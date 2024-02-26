import unittest
import sys
# append current directory to path
sys.path.append('..')

from eventTraceAnalysis import EventNode, Command

class TestEventTraceAnalysis(unittest.TestCase):
    def setUp(self):
        self.node = EventNode("", 0)

    def test_parseTimestamp(self):
        result = self.node.parseTimestamp("08:18:04.649921690 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventCreate_exit: { zeResult: ZE_RESULT_SUCCESS, phEvent_val: 0x0000556c1d012d80 }")
        # 8 hours, 18 minutes, and 4.649921690 seconds in seconds
        expected = 8*3600 + 18*60 + 4.649921690
        self.assertAlmostEqual(result, expected, places=7)

    def test_parseCommand_create(self):
        result = self.node.parseCommand("08:18:04.810841256 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventCreate_exit: { zeResult: ZE_RESULT_SUCCESS, phEvent_val: 0x0000556c1d012d80 }")
        self.assertEqual(result, ("0x0000556c1d012d80", Command.CREATE))

    def test_parseCommand_destroy(self):
        result = self.node.parseCommand("08:18:04.894961780 - cupcake - vpid: 267004, vtid: 267016 - lttng_ust_ze:zeEventDestroy_entry: { hEvent: 0x0000556c1d048a90 }")
        self.assertEqual(result, ("0x0000556c1d048a90", Command.DESTROY))

    def test_parseCommand_reset(self):
        result = self.node.parseCommand("08:18:04.810847676 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventHostReset_entry: { hEvent: 0x0000556c1d012d80 }")
        self.assertEqual(result, ("0x0000556c1d012d80", Command.RESET))

    def test_parseCommand_query(self):
        result = self.node.parseCommand("08:18:04.813072854 - cupcake - vpid: 267004, vtid: 267016 - lttng_ust_ze:zeEventQueryStatus_entry: { hEvent: 0x0000556c1d012d80 }")
        self.assertEqual(result, ("0x0000556c1d012d80", Command.QUERY))

    def test_parseCommand_signal(self):
        result = self.node.parseCommand("08:39:12.819069233 - cupcake - vpid: 3836181, vtid: 3836194 - lttng_ust_ze:zeEventHostSignal_entry: { hEvent: 0x00007f229802e9a0 }")
        self.assertEqual(result, ("0x00007f229802e9a0", Command.SIGNAL))

    def test_parseDependsOn_multiple(self):
        result = self.node.parseDependsOn("phWaitEvents_vals: [ 0x0000556c1d048370, 0x0000556c1d048371, 0x0000556c1d048372 ]")
        self.assertEqual(result, ["0x0000556c1d048370", "0x0000556c1d048371", "0x0000556c1d048372"])

    def test_parseDependsOn_single(self):
        result = self.node.parseDependsOn("phWaitEvents_vals: [ 0x0000556c1d048370 ]")
        self.assertEqual(result, ["0x0000556c1d048370"])

    def test_parseDependsOn_empty(self):
        result = self.node.parseDependsOn("phWaitEvents_vals: [ ]")
        self.assertEqual(result, [])
    
    def test_parseDependsOn_otherCommand(self):
        result = self.node.parseDependsOn("08:18:04.810847676 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventHostReset_entry: { hEvent: 0x0000556c1d012d80 }: ")
        self.assertEqual(result, [])

    def test_parseThreadId(self):
        result = self.node.parseThreadId("08:18:04.649921690 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventCreate_exit: { zeResult: ZE_RESULT_SUCCESS, phEvent_val: 0x0000556c1d012d80 }")
        self.assertEqual(result, "267004")

    def test_generate_node_map(self):
        pass

if __name__ == '__main__':
    unittest.main()