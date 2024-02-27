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
        elif "zeEventHostSynchronize_entry" in line:
            ptr = line.split("hEvent: ")[1].split(' ')[0]
            assert(ptr[-1] == ',')
            ptr = ptr[:-1]
            return ptr, Command.WAIT
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

class CircularDependencyError(Exception):
    def __init__(self, message="Circular dependency detected"):
        super().__init__(message)

def traverse_event_nodes_non_recursive(event_nodes):
    output = []
    stack = list(event_nodes)  # Use a list as a stack for nodes to be processed
    visited = set()  # Track visited nodes to detect cycles

    while stack:
        node = stack.pop()  # Get the last node from the stack
        if node in visited:
            # Detected a cycle, raise an exception
            raise CircularDependencyError(f"Circular dependuency detected at node with ptr {node.ptr}")
        visited.add(node)  # Mark node as visited

        if node.command != Command.SIGNAL:
            if node not in output:
                output.append(node)
        else:
            # Temporarily store nodes to keep the original order after SIGNAL nodes
            temp_nodes = []
            for dependency in reversed(node.dependsOn):  # Reverse to maintain order when adding to stack
                if dependency != "":
                    dep = NodeMap[dependency]
                    # Check if dependency is not already visited to prevent infinite loop
                    if dep[0] not in visited:
                        # Instead of recursive call, add dependency nodes to the stack
                        stack.extend(dep)
            # Add the current SIGNAL node after processing its dependencies
            if node not in output:
                temp_nodes.append(node)
            # Extend the output with processed nodes in the correct order
            output.extend(reversed(temp_nodes))

    return output

def event_reset_after_signal(ptr) -> bool:
    NodePtr = NodeMap[ptr]
    event_nodes = traverse_event_nodes_non_recursive(NodePtr)
    # sort by timestamp
    event_nodes.sort(key=lambda x: float(x.timestamp))
    # if there is a reset between the first occurence of signal and the first occurernce of wait, return True
    # 1. find the first occurence of singnal
    # 2. find the first occurence of wait
    # 3. check if a reset occurs between the two
    signal = None
    wait = None
    for i, node in enumerate(event_nodes):
        if node.command == Command.SIGNAL:
            signal = i
            break
    for i, node in enumerate(event_nodes):
        if node.command == Command.WAIT:
            wait = i
            break

    if signal is None or wait is None:
        return False
    for i in range(signal, wait):
        if event_nodes[i].command == Command.RESET:
            return True
    return False

def circular_dependency(ptr) -> bool:
    NodePtr = NodeMap[ptr]
    event_nodes = traverse_event_nodes_non_recursive(NodePtr)
    # sort by timestamp
    event_nodes.sort(key=lambda x: float(x.timestamp))

def all_events_signalled(ptr) -> bool:
    NodePtr = NodeMap[ptr]
    event_nodes = traverse_event_nodes_non_recursive(NodePtr)
    # sort by timestamp
    event_nodes.sort(key=lambda x: float(x.timestamp))
    # extract all unique ptr from the event_nodes
    unique_ptrs = set()
    for node in event_nodes:
        unique_ptrs.add(node.ptr)
    
    # # printout event_nodes
    # print("Event Nodes:")
    # for node in event_nodes:
    #     print(f"{node.ptr} {node.command} {node.timestamp}")
        

    # for every unique ptr, check if it is signalled
    for ptr in unique_ptrs:
        found_signal = False
        for node in event_nodes:
            if node.command == Command.SIGNAL:
                found_signal = True
                break
            else:
                return False
    return True

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
    
    NodeMap = generate_node_map(lines)
    reset_check = event_reset_after_signal("EventD")
    print(f"EventD reset after signal: {reset_check}")

    all_events_have_signal = all_events_signalled("EventD")
    print(f"EventD never signalled: {not all_events_have_signal}")
    pass