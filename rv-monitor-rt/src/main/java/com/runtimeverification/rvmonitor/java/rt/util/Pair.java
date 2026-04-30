package com.runtimeverification.rvmonitor.java.rt.util;

import java.util.List;

public class Pair {
    public EventNode node;
//    public String events;
//    public StringBuilder events;
    public List<String> events;
//    public Pair(EventNode node, String events) {
//    public Pair(EventNode node, StringBuilder events) {
    public Pair(EventNode node, List<String> events) {
        this.node = node;
        this.events = events;
    }
}
