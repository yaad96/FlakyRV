## Example: Timing-Dependent Flaky Test (TD)

This test is flaky because its outcome depends on timing. Variations in when operations are executed can lead to different outputs, resulting in inconsistent pass/fail behavior.

**Root cause:** The test compares outputs that include timestamps; if the two `save` calls occur within the same second, the test passes, otherwise it fails.


**Test snippet:**
```java
@Test
public void testSave() throws IOException {
    final String comments = "Hello world!";
    // actual
    try (ByteArrayOutputStream actual = new ByteArrayOutputStream()) {
        PropertiesFactory.EMPTY_PROPERTIES.save(actual, comments);
        // expected
        try (ByteArrayOutputStream expected = new ByteArrayOutputStream()) {
            PropertiesFactory.INSTANCE.createProperties().save(expected, comments);

            String expectedComment = getFirstLine(expected.toString("UTF-8"));
            String actualComment = getFirstLine(actual.toString("UTF-8"));
            assertEquals(expectedComment, actualComment);

            expected.reset();
            try (PrintStream out = new PrintStream(expected)) {
                new Properties().save(out, comments);
            }
            assertArrayEquals(expected.toByteArray(), actual.toByteArray());
        } catch (UnsupportedEncodingException e) {
            fail(e.getMessage(), e);
        }
    }
}
```

## Example: Implementation-Dependent Flaky Test (ID)

This test is flaky because it depends on the order of annotations returned by Java reflection, which is not guaranteed by the Java specification. As a result, different JVM executions may process annotations in different orders, leading to inconsistent test outcomes.

**Root cause:** The test assumes a fixed order of annotations, but `getDeclaredAnnotations()` returns them in arbitrary order.

**Test snippet:**
```java
@Test
public void apiOperationThenResponse() {
 SwaggerOperation swaggerOperation = swaggerOperations.findOperation("apiOperationThenResponse");
 List<String> tags = swaggerOperation.getOperation().getTags();
 MatcherAssert.assertThat(tags, contains("tag1", "tag2"));

 Response response = swaggerOperation.getOperation().getResponses().get("200");
 Assertions.assertEquals("200 is ok............", response.getDescription());
 Assertions.assertNull(response.getHeaders().get("x-user-domain"));
 Assertions.assertNotNull(response.getHeaders().get("x-user-name"));
}
```

## Example: Order-Dependent Flaky Test (OD)

This test is flaky because its outcome depends on the execution order of tests. Specifically, `testSetInstance_HdfsZooInstance_HostsGiven` fails when executed after `testSetInstance_HdfsZooInstance_InstanceGiven`.

**Root cause:** A process-wide singleton (`SiteConfiguration`) is initialized during the first test and not cleared. The second test reuses this stale state, leading to incorrect behavior and failed assertions.

**Test snippet:**
```java
@Test
public void testSetInstance_HdfsZooInstance_InstanceGiven() throws Exception {
  testSetInstance_HdfsZooInstance(false, true, false);
}

@Test
public void testSetInstance_HdfsZooInstance_HostsGiven() throws Exception {
  testSetInstance_HdfsZooInstance(false, false, true);
}
```

## Example: Non-Idempotent Outcome Flaky Test (NIO)

This test is flaky because its outcome changes when the same test is executed multiple times within the same JVM. The test relies on shared state (`PropertyBasedTests.LOGS`) that is modified during execution.

**Root cause:** The test reads from a shared log (`LOGS`) whose contents depend on prior executions. Since the state is not reset, repeated runs of the same test observe different values, leading to inconsistent outcomes.

**Test snippet:**
```java
@Test
public void orderingOfStatements() throws Exception {
    assertThat(testResult(PropertyBasedTests.class), failureCountIs(1));
    assertEquals(expectedStatements, PropertyBasedTests.LOGS);
}
```



