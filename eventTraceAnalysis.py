#!/usr/bin/env python3

# enum type for command which can be either create, reset, query
class Command:
    CREATE = 1
    RESET = 2
    QUERY = 3
    WAIT =4
    SIGNAL = 5
    DESTROY = 6


class EventNode:
    def __init__(self, line: str, line_idx: int):
        ptr, command = self.parseCommand(line)
        self.ptr = ptr
        self.next = None
        self.idx = line_idx
        self.line = line
        self.timestamp = self.parseTimestamp(line)  
        self.threadId = self.parseThreadId(line)
        self.command = command
        self.dependsOn = self.parseDependsOn(line)
    
    # given a timestamp like 08:18:04.649921690, parse it into an float seconds.milliseconds
    def parseTimestamp(self, t_string):
        t_string = t_string.split(' ')[0]
        t = t_string.split(':')
        seconds = float(t[0]) * 3600 + float(t[1]) * 60 + float(t[2])
        return seconds
    
    # 08:18:04.810841256 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventCreate_exit: { zeResult: ZE_RESULT_SUCCESS, phEvent_val: 0x0000556c1d012d80 }
    # 08:18:04.810847676 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventHostReset_entry: { hEvent: 0x0000556c1d012d80 } 
    # 08:18:04.894961780 - cupcake - vpid: 267004, vtid: 267016 - lttng_ust_ze:zeEventDestroy_entry: { hEvent: 0x0000556c1d048a90 }
    # 08:18:04.810847676 - cupcake - vpid: 267004, vtid: 267004 - lttng_ust_ze:zeEventHostReset_entry: { hEvent: 0x0000556c1d012d80 }
    # 08:18:04.813072854 - cupcake - vpid: 267004, vtid: 267016 - lttng_ust_ze:zeEventQueryStatus_entry: { hEvent: 0x0000556c1d012d80 }
    # 08:39:12.819069233 - cupcake - vpid: 3836181, vtid: 3836194 - lttng_ust_ze:zeEventHostSignal_entry: { hEvent: 0x00007f229802e9a0 }
    def parseCommand(self, line) -> tuple[str, Command]:
        if "zeEventCreate_exit" in line:
            # extract event from phEvent_val: 0x0000556c1d00e480
            ptr = line.split("phEvent_val: ")[1].split(' ')[0]
            return ptr, Command.CREATE
        elif "zeEventDestroy_entry" in line:
            # extract event from hEvent: 0x0000556c1d048a90
            ptr = line.split("hEvent: ")[1].split(' ')[0]
            return ptr, Command.DESTROY
        elif "zeEventHostReset_entry" in line:
            # extract event from hEvent: 0x0000556c1d012d80
            ptr = line.split("hEvent: ")[1].split(' ')[0]
            return ptr, Command.RESET
        elif "zeEventQueryStatus_entry" in line:
            ptr = line.split("hEvent: ")[1].split(' ')[0]
            return ptr, Command.QUERY 
        elif "zeEventHostSignal_entry" in line:
            ptr = line.split("hEvent: ")[1].split(' ')[0]
            return ptr, Command.SIGNAL
        
    def parseDependsOn(self, line) -> list[str]:
        # extract individual ptrs form phWaitEvents_vals: [ 0x0000556c1d048370, 0x0000556c1d048371, 0x0000556c1d048372 ]
        # phWaitEvents_vals: [  ] }
        if "phWaitEvents_vals: " not in line:
            return []
        if "phWaitEvents_vals: [ ]" in line:
            return []
        else:
            return [ptr for ptr in line.split('[ ')[1].split(' ]')[0].split(', ')]

    def parseThreadId(self, line) -> str:
        return line.split(' ')[7].split(',')[1]
    
class NodeProcessor:
    def __init__(self, ptr, lines):
        self.ptr = ptr
        self.lines = lines
        self.head = None
        self.tail = None
        self.generateHeadNode()
    
    def generateHeadNode(self):
        # go through lines generating nodes until a node with command.CREATE is found
        for i, line in enumerate(self.lines):
            if "zeEventCreate_exit" in line and self.ptr in line:
                self.head = EventNode(line, i)
                self.tail = self.head
                break

# main
if __name__ == "__main__":
    # two arguments: ptr, and path to trace file
    import sys
    if len(sys.argv) != 3:
        print("Usage: python3 eventTraceAnalysis.py <ptr> <trace_file>")
        sys.exit(1)
    ptr = sys.argv[1]
    trace_file = sys.argv[2]
    # read file
    with open(trace_file, 'r') as f:
        lines = f.readlines()
    
    processor = NodeProcessor(ptr, lines)