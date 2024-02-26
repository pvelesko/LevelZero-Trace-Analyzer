#!/usr/bin/env python3
import re
from typing import List
from enum import Enum

class Command(Enum):
    CREATE = 1
    RESET = 2
    QUERY = 3
    WAIT = 4
    SIGNAL = 5
    DESTROY = 6

    def __repr__(self):
        return self.name

class EventNode:
    def __init__(self, line: str, line_idx: int):
        self.ptr, self.command = self.parseCommand(line)
        self.next = None
        self.idx = line_idx
        self.line = line
        self.timestamp = self.parseTimestamp(line)  
        self.threadId = self.parseThreadId(line)
        self.dependsOn = self.parseDependsOn(line)
    
    # given a timestamp like 08:18:04.649921690, parse it into an float seconds.milliseconds
    def parseTimestamp(self, t_string):
        t_string = t_string.split(' ')[0]
        t = t_string.split(':')
        if len(t) != 3:
            return None
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
        elif "hSignalEvent" in line:
            ptr = line.split("hSignalEvent: ")[1].split(' ')[0]
            # make sure the last char is , and drop it
            assert(ptr[-1] == ',')
            ptr = ptr[:-1]
            return ptr, Command.SIGNAL
        else:
            return None, None
        
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
        matches = re.findall(r'vtid: \d+', line)
        if len(matches) == 0:
            return None
        return matches[0].split(' ')[1]

def generate_node_map(lines: list[str]) -> dict[str, list[EventNode]]:
    node_map = {}
    for i, line in enumerate(lines):
        node = EventNode(line, i)
        if node.ptr is None:
            continue
        if node.ptr not in node_map:
            node_map[node.ptr] = [node]
        else:
            node_map[node.ptr].append(node) 
    return node_map

def traverse_event_nodes(event_nodes):
    output = []
    for node in event_nodes:
        if node.command != Command.SIGNAL:
            output.append(node)
        else:
            for dependency in node.dependsOn:
                if dependency != "":
                    dep = NodeMap[dependency]
                    output.extend(traverse_event_nodes(dep))
            output.append(node)
    return output

def traverse_event_nodes_non_recursive(event_nodes):
    output = []
    stack = list(event_nodes)  # Use a list as a stack for nodes to be processed

    while stack:
        node = stack.pop()  # Get the last node from the stack
        if node.command != Command.SIGNAL:
            output.append(node)
        else:
            # Temporarily store nodes to keep the original order after SIGNAL nodes
            temp_nodes = []
            for dependency in reversed(node.dependsOn):  # Reverse to maintain order when adding to stack
                if dependency != "":
                    dep = NodeMap[dependency]
                    # Instead of recursive call, add dependency nodes to the stack
                    stack.extend(dep)
            # Add the current SIGNAL node after processing its dependencies
            temp_nodes.append(node)
            # Extend the output with processed nodes in the correct order
            output.extend(reversed(temp_nodes))
    return output

if __name__ == "__main__":
    # # two arguments: ptr, and path to trace file
    # import sys
    # if len(sys.argv) != 3:
    #     print("Usage: python3 eventTraceAnalysis.py <ptr> <trace_file>")
    #     sys.exit(1)
    # ptr = sys.argv[1]
    # trace_file = sys.argv[2]
    # # read file
    trace_file = "/Users/pvelesko/local/LevelZero-Trace-Analyzer/simple.trace"
    with open(trace_file, 'r') as f:
        lines = f.readlines()
    
    NodeMap = generate_node_map(lines)
    NodeA = NodeMap["EventA"]
    NodeB = NodeMap["EventB"]
    NodeC = NodeMap["EventC"]

    test = traverse_event_nodes_non_recursive(NodeC)
    test.reverse()
    # sort test by timestamp
    test.sort(key=lambda x: x.timestamp)
    for node in test:
        print(f"NodeC: {node.command} {node.ptr} {node.dependsOn} {node.timestamp} {node.threadId}")

    print("\n\n")
    test = traverse_event_nodes(NodeC)
    test.sort(key=lambda x: x.timestamp)
    for node in test:
        print(f"NodeC: {node.command} {node.ptr} {node.dependsOn} {node.timestamp} {node.threadId}")
    pass