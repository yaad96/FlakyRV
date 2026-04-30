package com.runtimeverification.rvmonitor.java.rt.table.tracefb;

import java.util.HashMap;

public class FbEventNode {
    public boolean activated = false;
    public HashMap<String, FbEventNode> children = new HashMap<>();

    public FbEventNode getNextNodeAfterSeeingEvent(String event) {
        if (children.containsKey(event)) {
	    return children.get(event);
        }
        FbEventNode nextEvent = new FbEventNode();
        children.put(event, nextEvent);
        return nextEvent;
    }
}
