package com.runtimeverification.rvmonitor.java.rt.util;

import java.io.File;
import java.sql.Clob;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;

import org.h2.tools.Csv;

import javax.sql.rowset.serial.SerialClob;

public class TraceDBNone implements TraceDB {

    private int i = 0;
    public TraceDBNone() {
        updateSystemProperty();
    }

    @Override
    public void put(String monitorID, String trace, int length) {
        i++;
    }

    /**
     * Update system properties to include dbDir information so that JUnit Listeners that work on the DB have access.
     */
    private void updateSystemProperty() {
        System.err.println("[TraceDBNONE] Set dbFilePath to: NONE");
    }

    @Override
    public void update(String monitorID, String trace, int length) {
        i++;
    }


    @Override
    public void createTable() {

    }

    @Override
    public int uniqueTraces() {
        return i;
    }

    @Override
    public int size() {
        return i;
    }

    @Override
    public List<Integer> getTraceLengths() {
        return new ArrayList<>();
    }

    @Override
    public Map<String, Integer> getTraceFrequencies() {
        return new HashMap<>();
    }

    @Override
    public void dump() {

    }
}
