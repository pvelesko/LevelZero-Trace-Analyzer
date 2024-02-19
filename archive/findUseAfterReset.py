import re

def extract_pointers(lines) -> list:
    # extract all unique events phEvent_val: 0x000055eaeb933670
    ptr_extract_regex = re.compile(r"phEvent_val: (0x[0-9a-fA-F]+)")
    pointers = []
    for line in lines:
        match = ptr_extract_regex.search(line)
        if match:
            pointers.append(match.group(1))

    return list(set(pointers))


def extract_pointer_history(lines, pointer) -> list:
    # extract all lines that contain the pointer
    return [line for line in lines if pointer in line]

def trim_history(lines, cmd) -> list:
    # drop all lines that contain cmd
    return [line for line in lines if cmd not in line]


def parse_signal_event(line):
    if "hSignalEvent" in line:
        d =   DependencyNode(line.split(f"hSignalEvent: ")[1].split(",")[0])
        d.signal_line = line
        return d
    elif "zeCommandListAppendSignalEvent_entry" in line:
        d = DependencyNode(line.split(f"hEvent: ")[1].split(" ")[0])
        d.signal_line = line
        return d
    else:
        return None

def parse_wait_events(line):
    wait_for_ptrs = []
    if "phWaitEvents_vals: [  ]" in line:
        return []
    if  "phWaitEvents_vals" in line:
        l = line.split("phWaitEvents_vals: [")[1].split("]")[0]
        wait_for_ptrs = l.split(", ")
        # trim whitespace
        wait_for_ptrs = [x.strip() for x in wait_for_ptrs]
        # convert to DependencyNode
        wait_for_ptrs = [DependencyNode(x) for x in wait_for_ptrs]
    return wait_for_ptrs

class DependencyNode:
    def __init__(self, value):
        self.value = value
        self.signal_line = None
        self.signal_line_idx = None
        self.wait_lines = []
        self.dependencies = []
    def circular_dep_check(self, node):
        dep_nodes = []
        self.dfs([dep_nodes])
        if node in dep_nodes:
            return True 
        return False

    def add_dependency(self, node):
        if self.circular_dep_check(node):
            print(f"Error: Circular dependency detected, {node.value} is already in the dependency chain")
            return
        # print(f"Event {self.value} depends on {node}")
        self.dependencies.append(node)

    def dfs(self, visited):
        #print(f"Visiting {self.value}: {self.line}")
        if self in visited:
            return
        visited.append(self)
        for d in self.dependencies:
            d.dfs(visited)

    def __repr__(self):
        return f"Event({self.value})"

def find_dependency_chain(lines, ptr) -> map:  
    # create a map for dependency chains by name
    nodes = {}

    while len(lines) > 0:
        idx = len(lines) - 1
        current_line = lines.pop()
        # print(f"Processing line: {current_line}")
        signal = parse_signal_event(current_line)
        if signal and signal.value not in nodes:
            signal.signal_line_idx = idx
            nodes[signal.value] = signal
        elif signal:
            signal = nodes[signal.value]
            signal.signal_line = current_line
            signal.signal_line_idx = idx   
        # elif "zeEventCreate_exit" in current_line and ptr in current_line:
        else:
            continue

        wait_events = parse_wait_events(current_line)
        for w in wait_events:
            if w.value not in nodes:
                nodes[w.value] = w
            else:
                w = nodes[w.value]
            signal.add_dependency(w)
        # print(f"node: {signal.value} with dependencies: {signal.dependencies}")
    return nodes

def get_lines_between_idx(lines, start , end):
    start_idx = lines.index(start.line)
    end_idx = lines.index(end.line)
    return lines[start_idx:end_idx]

def check_lines_for_event_reset(lines, nodes):
    for node in nodes:
        for line in lines:
            if "zeEventHostReset_entry" in line and node.value in line:
                return line
    return None

if __name__ == "__main__":
    # Example file_path, replace with the path to your trace file
    import sys
    # sys.setrecursionlimit(10000)  # Set to a higher value as needed
    file = sys.argv[1]
    ptr = sys.argv[2]
    with open(file, 'r') as f:
        lines = f.readlines()
    lines = trim_history(lines, "zeEventQueryStatus")
    lines = trim_history(lines, "event_profiling")
    if(len(lines) == 0):
        print("No lines found in file")
        exit(1)
    lines_reverse = lines
    lines_reverse.reverse()

    deps = find_dependency_chain(lines_reverse, ptr)
    print("\n\n")
    node = deps[ptr]

    # find the index of the 
    all_nodes = []
    node.dfs(all_nodes)
    highest_line = 0
    for n in all_nodes:
        if n.signal_line_idx and n.signal_line_idx > highest_line:
            highest_line = n.signal_line_idx
    
    for node in all_nodes:
        print(f"{node.signal_line}")
    between = lines_reverse[node.signal_line_idx:highest_line]
    dep_chain_broken = check_lines_for_event_reset(between, all_nodes)
    print(f"Dependency chain broken: {dep_chain_broken}")