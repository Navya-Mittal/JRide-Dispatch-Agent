package com.navya.dispatchengine.sim;

import com.navya.dispatchengine.api.DispatchHttpServer;
import com.navya.dispatchengine.engine.DispatchEngine;
import com.navya.dispatchengine.engine.DispatchResult;
import com.navya.dispatchengine.engine.ZoneSnapshot;
import com.navya.dispatchengine.model.Driver;
import com.navya.dispatchengine.model.RideRequest;

import static com.navya.dispatchengine.sim.DublinLocations.*;

/**
 * Demo entry point, scripted around real Dublin locations.
 *
 * <pre>
 *   java -jar target/ride-dispatch-engine.jar            # scripted walkthrough demo
 *   java -jar target/ride-dispatch-engine.jar --server    # starts REST API on :8080
 * </pre>
 */
public final class Main {

    private static final String REGION = "Dublin";

    public static void main(String[] args) throws Exception {
        if (args.length > 0 && args[0].equals("--server")) {
            int port = 8080;
            int drivers = 150;
            for (int i = 1; i + 1 < args.length; i += 2) {
                if (args[i].equals("--port")) port = Integer.parseInt(args[i + 1]);
                else if (args[i].equals("--drivers")) drivers = Integer.parseInt(args[i + 1]);
            }
            runServer(port, drivers);
        } else {
            runScriptedDemo();
        }
    }

    private static void runScriptedDemo() {
        System.out.println("=== Ride Dispatch Engine - Dublin walkthrough ===\n");

        DispatchEngine engine = new DispatchEngine();
        engine.addMatchListener(match -> System.out.println("  MATCHED: " + match));

        System.out.println("1) Two drivers come online near Trinity College and Grafton Street:");
        driverOnline(engine, "driver-aoife", TRINITY_COLLEGE);
        driverOnline(engine, "driver-cian", GRAFTON_STREET);
        printZone(engine);

        System.out.println("2) A rider requests a pickup near Temple Bar (walking distance from both drivers):");
        DispatchResult result1 = requestRide(engine, "rider-saoirse", TEMPLE_BAR, O_CONNELL_STREET);
        printResult(result1);
        printZone(engine);

        System.out.println("3) A rider requests a pickup at Dublin Airport, far from any online driver:");
        DispatchResult result2 = requestRide(engine, "rider-oisin", DUBLIN_AIRPORT, IFSC);
        printResult(result2);
        printZone(engine);
        System.out.println("   (no driver within the search radius -> request is queued, not lost)\n");

        System.out.println("4) A driver comes online near the airport - the queued request is matched automatically:");
        driverOnline(engine, "driver-niamh", DUBLIN_AIRPORT);
        printZone(engine);

        System.out.println("5) driver-aoife drops off their rider near Croke Park and becomes available again:");
        engine.completeRide(REGION, "driver-aoife", CROKE_PARK).join();
        printZone(engine);

        System.out.println("Run with --server to expose the same engine over a REST API on :8080.");
        engine.shutdown();
    }

    private static void runServer(int port, int drivers) throws Exception {
        DispatchEngine engine = new DispatchEngine();
        engine.addMatchListener(match -> System.out.println("MATCHED " + match));

        DispatchSimulator simulator = new DispatchSimulator(engine, REGION, 42);
        if (drivers > 0) simulator.seedDrivers(drivers);

        DispatchHttpServer server = new DispatchHttpServer(engine, port);
        server.start();
        System.out.println("REST API listening on http://localhost:" + port + "  (region=" + REGION + ", " + drivers + " drivers seeded)");
        System.out.println("Try:");
        System.out.println("  curl \"http://localhost:8080/zone/status?region=Dublin\"");
        System.out.println("  curl -X POST \"http://localhost:8080/riders/request?region=Dublin&riderId=r1&pickupLat=53.3438&pickupLon=-6.2546&destLat=53.3498&destLon=-6.2603\"");
        System.out.println("  curl -X POST \"http://localhost:8080/drivers/online?region=Dublin&driverId=d999&lat=53.3438&lon=-6.2546\"");
        System.out.println("Press Ctrl+C to stop.");

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            server.stop();
            engine.shutdown();
        }));
    }

    private static void driverOnline(DispatchEngine engine, String driverId, com.navya.dispatchengine.model.Location location) {
        engine.driverOnline(REGION, new Driver(driverId, location)).join();
    }

    private static DispatchResult requestRide(DispatchEngine engine, String riderId,
                                               com.navya.dispatchengine.model.Location pickup,
                                               com.navya.dispatchengine.model.Location destination) {
        RideRequest request = new RideRequest(riderId, REGION, pickup, destination);
        return engine.requestRide(request).join();
    }

    private static void printResult(DispatchResult result) {
        if (result.isMatched()) {
            System.out.printf("   -> matched with %s (%.2f km away, found within ring %d)%n",
                    result.getMatch().getDriverId(), result.getMatch().getDriverDistanceKm(), result.getMatch().getRingsSearched());
        } else {
            System.out.println("   -> no driver available yet, request queued (status=" + result.getRequest().getStatus() + ")");
        }
    }

    private static void printZone(DispatchEngine engine) {
        ZoneSnapshot snapshot = engine.snapshot(REGION).join();
        System.out.printf("   [Zone: %s] drivers=%d (available=%d, en route=%d), pending riders=%d%n%n",
                snapshot.region(), snapshot.totalDrivers(), snapshot.availableDrivers(),
                snapshot.enRouteDrivers(), snapshot.pendingRequests());
    }
}
