#!/usr/bin/env python3

import os
import sys
import xml.etree.ElementTree as ET


if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
    print('Usage: python get_junit_testcases.py <TEST-TestSuite.xml>')
    exit(1)

with open(sys.argv[1]) as f:
    tree = ET.parse(f)
    suite = tree.getroot()
    for testcase in suite.findall('testcase'):
        if testcase.get('classname') and testcase.get('name') and testcase.find('skipped') is None:
            print(testcase.get('classname') + '#' + testcase.get('name'))
