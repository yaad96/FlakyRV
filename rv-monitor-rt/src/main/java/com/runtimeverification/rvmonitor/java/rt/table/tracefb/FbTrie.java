package com.runtimeverification.rvmonitor.java.rt.table.tracefb;

import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

public class FbTrie {
    private final FbEventNode root = new FbEventNode();
    private final HashMap<String, FbEventNode> locFbMap = new HashMap<>();

    ReentrantLock lock = new ReentrantLock();

    public boolean checkUniq(String creationLoc) {
	FbEventNode node = locFbMap.get(creationLoc);
	if (node == null || !node.activated) {
	    return true;
	}
	return false;
    }

    public void finalizedTrace(String creationLoc) {
	FbEventNode node = locFbMap.get(creationLoc);
	if (node != null) {
    	    node.activated = true;
	}
    }

    public void clearFb(String creationLoc) {
        locFbMap.put(creationLoc, null);
    }

    public void addEvent(String creationLoc, String event) {
        lock.lock();
        FbEventNode node = locFbMap.get(creationLoc);

        if (node != null) {
            node = node.getNextNodeAfterSeeingEvent(event);
        } else {
            node = root.getNextNodeAfterSeeingEvent(event);
        }
        locFbMap.put(creationLoc, node);
        lock.unlock();
    }
}
