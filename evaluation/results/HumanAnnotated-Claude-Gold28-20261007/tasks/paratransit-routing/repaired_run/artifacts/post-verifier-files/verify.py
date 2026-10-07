#!/usr/bin/env python3
"""Independent verifier replicating the problem's feasibility rules."""
import csv, json

OP_LO, OP_HI, SHIFT, TW, CAP, SERVICE = 300, 1320, 480, 30, 3, 5
SHIFT_STARTS = set(range(300, 840 + 1, 60))


def main():
    with open("/root/requests.json") as f:
        reqs = json.load(f)
    with open("/root/t_matrix.csv") as f:
        M = [[int(x) for x in r] for r in csv.reader(f)]
    with open("/root/report.json") as f:
        rep = json.load(f)
    trips = []
    passenger_of_trip = []
    pass_sets = []
    for pi, p in enumerate(reqs):
        s = []
        for t in p["trips"]:
            s.append(len(trips))
            trips.append(t)
            passenger_of_trip.append(pi)
        pass_sets.append(s)
    n = len(trips)
    end_depot = 2 * n + 1

    served_trips_global = set()
    pickup_assigned = {}
    issues = []
    for ridx, route in enumerate(rep["routes"]):
        vid = route["vehicle_id"]
        st = route["start_time"]
        seq = route["node_sequence"]
        if st not in SHIFT_STARTS:
            issues.append((vid, f"start_time {st} not on hourly grid"))
        if seq[0] != 0:
            issues.append((vid, f"first node {seq[0]} != 0"))
        if seq[-1] != end_depot:
            issues.append((vid, f"last node {seq[-1]} != {end_depot}"))
        cur = st
        load = 0
        pending = {}
        local_served = set()
        for i in range(len(seq) - 1):
            node = seq[i]; nxt = seq[i+1]
            if node == 0 or node == end_depot:
                # depot: no service
                departure = cur
            else:
                if 1 <= node <= n:
                    # pickup
                    tid = node - 1
                    ea = trips[tid]["expected_arrival_time"]
                    direct = M[node][node + n]
                    if direct < 0:
                        issues.append((vid, f"invalid direct pu->do for trip {tid}"))
                    lo = ea - TW - direct
                    hi = ea - direct
                    if cur > hi:
                        issues.append((vid, f"pu trip {tid} arrival {cur} > hi {hi}")); break
                    service_start = max(cur, lo)
                    departure = service_start + SERVICE
                    load += 1
                    if load > CAP:
                        issues.append((vid, f"capacity exceeded {load}")); break
                    if tid in pending:
                        issues.append((vid, f"pickup trip {tid} already pending")); break
                    pending[tid] = True
                    if tid in pickup_assigned:
                        issues.append((vid, f"trip {tid} already picked up by {pickup_assigned[tid]}"))
                    pickup_assigned[tid] = vid
                elif n + 1 <= node <= 2 * n:
                    tid = node - n - 1
                    ea = trips[tid]["expected_arrival_time"]
                    lo = ea - TW
                    hi = ea
                    if cur > hi:
                        issues.append((vid, f"do trip {tid} arrival {cur} > hi {hi}")); break
                    if tid not in pending:
                        issues.append((vid, f"dropoff trip {tid} not pending")); break
                    service_start = max(cur, lo)
                    departure = service_start + SERVICE
                    load -= 1
                    if load < 0:
                        issues.append((vid, f"negative load")); break
                    local_served.add(tid)
                    del pending[tid]
                else:
                    issues.append((vid, f"bad node id {node}")); break
            travel = M[node][nxt]
            if travel < 0:
                issues.append((vid, f"negative arc {node}->{nxt}")); break
            cur = departure + travel
        else:
            # end-of-loop checks
            if cur > OP_HI:
                issues.append((vid, f"route ends at {cur} > {OP_HI}"))
            if cur - st > SHIFT:
                issues.append((vid, f"route length {cur-st} > {SHIFT}"))
            if load != 0:
                issues.append((vid, f"final load {load} != 0"))
            if pending:
                issues.append((vid, f"pending dropoffs left: {pending}"))
            served_trips_global |= local_served
    # Group feasibility: a passenger set counts only if all trips served
    group_served_trips = 0
    group_served_sets = 0
    for s in pass_sets:
        if all(t in served_trips_global for t in s):
            group_served_sets += 1
            group_served_trips += len(s)
        else:
            # if any partial, those served trips do not count
            pass
    # Check for partial sets (would mean problem invalid per rules)
    partial = 0
    for s in pass_sets:
        srv = [t for t in s if t in served_trips_global]
        if 0 < len(srv) < len(s):
            partial += 1
    print(f"total routes in report: {len(rep['routes'])}")
    print(f"individual trips found served: {len(served_trips_global)}")
    print(f"group-served sets: {group_served_sets}, group-served trips: {group_served_trips}")
    print(f"partial sets (should be 0): {partial}")
    print(f"issues: {len(issues)}")
    for it in issues[:20]:
        print("  ", it)


if __name__ == "__main__":
    main()
