package com.runtimeverification.rvmonitor.java.rt.observable;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.List;
import java.util.Properties;
import java.util.Set;

import com.runtimeverification.rvmonitor.java.rt.ref.CachedWeakReference;
import com.runtimeverification.rvmonitor.java.rt.tablebase.AbstractIndexingTree;
import com.runtimeverification.rvmonitor.java.rt.tablebase.AbstractMonitor;
import com.runtimeverification.rvmonitor.java.rt.tablebase.AbstractMonitorSet;
import com.runtimeverification.rvmonitor.java.rt.tablebase.AbstractPartitionedMonitorSet;
import com.runtimeverification.rvmonitor.java.rt.tablebase.IDisableHolder;
import com.runtimeverification.rvmonitor.java.rt.tablebase.IIndexingTreeValue;
import com.runtimeverification.rvmonitor.java.rt.tablebase.IMonitor;
import com.runtimeverification.rvmonitor.java.rt.util.*;

public class MonitorTraceCollector implements IInternalBehaviorObserver {

    protected final PrintWriter writer;

    protected final TraceDB traceDB;

    protected final Set<String> monitors;

    private boolean dbConfigLoaded;

    protected Properties configs;

    private boolean isDumpingTraces;

    protected String dbConfPath;

    public MonitorTraceCollector(PrintWriter writer, String dbPath, String dbConfPath) {
        this.writer = writer;
        this.monitors = new HashSet<>();
        this.dbConfPath = dbConfPath;
        loadDBConfig();
        // TODO: CLEAN THIS UP
//        this.traceDB = getTraceDB(dbPath);
        this.traceDB = TraceDatabase.getInstance();
        setDumpingTraces(getDumpConfig());
        traceDB.createTable();
    }

    private boolean getDumpConfig() {
        boolean isDumping = false;
        if (isDbConfigLoaded()) {
            Properties userConfigs = loadDBConfig();
            if (userConfigs.containsKey("dumpDB")) {
                String dump = userConfigs.getProperty("dumpDB");
                switch (dump) {
                    case "true" :
                        isDumping = true;
                        break;
                    case "false":
                    default:
                        isDumping = false;
                }
            }
        }
        return isDumping;
    }

    private Properties loadDBConfig() {
        if (isDbConfigLoaded()) {
            return configs;
        }
        configs = new Properties();
        File traceDBConfigFile = new File(dbConfPath);
        if (traceDBConfigFile.exists()) {
            try(FileInputStream inputStream = new FileInputStream(traceDBConfigFile)) {
                configs.load(inputStream);
                setDbConfigLoaded(true);
            } catch (FileNotFoundException e) {
                e.printStackTrace();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        return configs;
    }

    private TraceDB getTraceDB(String dbPath) {
        TraceDB traceDB = null;
        if (isDbConfigLoaded()) {
            Properties userConfigs = loadDBConfig();
            if (userConfigs.containsKey("db")) {
                String dbType = userConfigs.getProperty("db");
                switch (dbType) {
                    case "h2":
                        traceDB = new TraceDBH2(dbPath);
                        break;
                    case "h2-normalized":
                        traceDB = new TraceDBH2Normalized(dbPath);
                        break;
                    case "sqlite":
                        traceDB = new TraceDBSQLite(dbPath);
                        break;
                    case "memory":
                        traceDB = new TraceDBMemory();
                        break;
                    case "none":
                        traceDB = new TraceDBNone();
                        break;
                    default:
                        traceDB = new TraceDBH2(dbPath);
                }
            }
        }

        // some problem occurred while reading from config; use the default
        if (traceDB == null) {
            traceDB = new TraceDBH2Normalized(dbPath);
        }

        return traceDB;
    }

    public boolean isDbConfigLoaded() {
        return dbConfigLoaded;
    }

    public void setDbConfigLoaded(boolean dbConfigLoaded) {
        this.dbConfigLoaded = dbConfigLoaded;
    }

    public boolean isDumpingTraces() {
        return isDumpingTraces;
    }

    public void setDumpingTraces(boolean dumpingTraces) {
        this.isDumpingTraces = dumpingTraces;
    }


    @Override
    public void onMonitorTransitioned(AbstractMonitor monitor) {
//        insertOrUpdate(monitor.getClass().getSimpleName() + "#" + monitor.monitorid, monitor.trace.toString(), monitor.trace.size());
//        insert(monitor.getClass().getSimpleName() + "#" + monitor.monitorid, monitor.trace);
    }

    private void insert(String monitorID, List<String> trace) {
        traceDB.replace(monitorID, trace);
    }

    private void insertOrUpdate(String monitorID, String trace, int length) {
        if (monitors.add(monitorID)) {
            traceDB.put(monitorID, trace, length);
        } else {
            traceDB.update(monitorID, trace, length);
        }
    }

    @Override
    public <TMonitor extends IMonitor> void onMonitorTransitioned(AbstractMonitorSet<TMonitor> set) {
        for (int i = 0; i < set.getSize(); ++i) {
            // AbstractMonitor is the only parent of all monitor types and it implements IMonitor
//            AbstractMonitor monitor = (AbstractMonitor) set.get(i);
//            insertOrUpdate(monitor.getClass().getSimpleName() + "#" + monitor.monitorid, monitor.trace.toString(), monitor.trace.size());
//            insert(monitor.getClass().getSimpleName() + "#" + monitor.monitorid, monitor.trace);
        }
    }

    @Override
    public <TMonitor extends IMonitor> void onMonitorTransitioned(AbstractPartitionedMonitorSet<TMonitor> set) {
        for (AbstractPartitionedMonitorSet<TMonitor>.MonitorIterator i = set.monitorIterator(true); i.moveNext(); ) {
            // AbstractMonitor is the only parent of all monitor types and it implements IMonitor
//            AbstractMonitor monitor = (AbstractMonitor) i.getMonitor();
//            insertOrUpdate(monitor.getClass().getSimpleName() + "#" + monitor.monitorid, monitor.trace.toString(), monitor.trace.size());
//            insert(monitor.getClass().getSimpleName() + "#" + monitor.monitorid, monitor.trace);
        }
    }

    @Override
    public void onCompleted() {

    }

    // TODO: We do not use any of the following methods; what's the runtime cost of keeping them?
    @Override
    public void onEventMethodEnter(String evtname, Object... args) {

    }

    @Override
    public void onIndexingTreeCacheHit(String cachename, Object cachevalue) {

    }

    @Override
    public void onIndexingTreeCacheMissed(String cachename) {

    }

    @Override
    public void onIndexingTreeCacheUpdated(String cachename, Object cachevalue) {

    }

    @Override
    public <TWeakRef extends CachedWeakReference, TValue extends IIndexingTreeValue> void onIndexingTreeLookup(AbstractIndexingTree<TWeakRef, TValue> tree, LookupPurpose purpose, Object retrieved, Object... keys) {

    }

    @Override
    public <TWeakRef extends CachedWeakReference, TValue extends IIndexingTreeValue> void onTimeCheck(AbstractIndexingTree<TWeakRef, TValue> tree, IDisableHolder source, IDisableHolder candidate, boolean definable, Object... keys) {

    }

    @Override
    public <TWeakRef extends CachedWeakReference, TValue extends IIndexingTreeValue> void onIndexingTreeNodeInserted(AbstractIndexingTree<TWeakRef, TValue> tree, Object inserted, Object... keys) {

    }

    @Override
    public void onNewMonitorCreated(AbstractMonitor created) {

    }

    @Override
    public void onMonitorCloned(AbstractMonitor existing, AbstractMonitor created) {
        // Copy traces
//        traceDB.cloneMonitor(existing.getClass().getSimpleName() + "#" + existing.monitorid, created.getClass().getSimpleName() + "#" + created.monitorid);
    }

    @Override
    public void onDisableFieldUpdated(IDisableHolder affected) {

    }

    @Override
    public void onEventMethodLeave() {

    }
}

