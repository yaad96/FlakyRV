package com.runtimeverification.rvmonitor.java.rt.table.tracefb;

import java.util.*;

public class FbManager {
    private FbTrie fbTrie = new FbTrie();
    private HashMap<String, FbStatus> statusMap = new HashMap<String, FbStatus>();

    public boolean ifUniqTrace(String creationLoc) {
        if (!(statusMap.containsKey(creationLoc))) {
	    statusMap.put(creationLoc, new FbStatus());
	    return false;
	}
	FbStatus fbStatus = statusMap.get(creationLoc);
	return fbStatus.ifUniqTrace();
    }

    public boolean createMonitor(String creationLoc) {
	FbStatus fbStatus = statusMap.get(creationLoc);

	if (fbTrie.checkUniq(creationLoc)) {
	    boolean lastActivated = fbStatus.processUniq();
	    if (lastActivated) {
	        fbTrie.finalizedTrace(creationLoc);
	    }
	    fbTrie.clearFb(creationLoc);
	    return true;
	} else {
	    fbTrie.clearFb(creationLoc);
	    return fbStatus.processDup();
        }
    } 

    public void addEvent(String creationLoc, String event) {
    	fbTrie.addEvent(creationLoc, event);
    }
}
