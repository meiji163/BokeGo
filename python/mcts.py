from abc import ABC, abstractmethod
from collections import defaultdict
import math

from bokeNet import ValueNet, value

EXPAND_THRESH = 10

class MCTS:
    "Monte Carlo tree searcher. First rollout the tree then choose a move."

    def __init__(self, value_net: ValueNet=None, exploration_weight=1, value_net_weight=0.5):
        self.Q = defaultdict(int)  # total reward of each node
        self.N = defaultdict(int)  # total visit count for each node
        self.V = defaultdict(int)  # accumulated value net evaluations
        self.children = dict()  # children of each node
        self.value_net = value_net
        self.exploration_weight = exploration_weight
        self.value_net_weight = value_net_weight
        self.winrate = None 

    def choose(self, node):
        "Choose the best successor of node. (Choose a move in the game)"
        if node.is_terminal():
            raise RuntimeError(f"choose called on terminal node {node}")

        if node not in self.children:
            return node.find_random_child()

        def score(n):
            if self.N[n] == 0:
                return float("-inf")  # avoid unseen moves
            return self.N[n]

        # Choose most visited node
        best = max(self.children[node], key=score)
        self.winrate = self.Q[best]/self.N[best]
        print(self.winrate)
        return best

    def do_rollout(self, node, n = 1):
        "Train for n iterations"
        for _ in range(n):
            # Get path to leaf of current search tree
            path = self._descend(node)
            leaf = path[-1]
            leaf_val = value(self.value_net, leaf, device = leaf.device)
            # Get result of rollout starting from leaf
            score = self._simulate(leaf)
            self._backpropagate(path, score, leaf_val)

    def _descend(self, node):
        "Return a path from root down to leaf via PUCT selection"
        # Start at root (current position)
        path = [node]
        while True:
            # Is node a leaf?
            if node not in self.children or not self.children[node]:
                # Heuristic: if node is "promising" (i.e. large # of visits),
                # expand search tree to include node's children
                if self.N[node] > EXPAND_THRESH:
                    self._expand(node)
                return path
            node = self._puct_select(node)  # descend a layer deeper
            path.append(node)

    def _expand(self, node):
        "Update the `children` dict with the children of `node`"
        if node in self.children:
            return  # already expanded
        self.children[node] = node.find_children()

    # Need to make this faster (ideally at least 10x)
    def _simulate(self, node):
        "Returns the reward for a random simulation (to completion) of `node`"
        invert_reward = not node.color
        while True:
            if node.is_terminal():
                reward = node.reward()
                reward = invert_reward^reward
                return reward
            node = node.find_random_child()

    def _backpropagate(self, path, reward, leaf_val):
        "Send the reward back up to the ancestors of the leaf"
        for node in reversed(path):
            self.N[node] += 1
            self.Q[node] += reward
            self.V[node] += leaf_val
            reward = 1 - reward

    def _puct_select(self, node):
        "Select a child of node with PUCT"

        # Predictor + UCT (PUCT) variant used in AlphaGo
        total_visits = sum(self.N[n] for n in self.children[node])
        # First visit selects policy's top choice
        if total_visits == 0:
            total_visits = 1
        if not node.dist:
            node.set_dist()
        def puct(n):
            last_move_prob = node.dist.probs[n.last_move].item()
            avg_reward = 0 if self.N[n] == 0 else ((1 - self.value_net_weight) * self.Q[n]
                                                    + self.value_net_weight * self.V[n]) / self.N[n]
            return avg_reward + (self.exploration_weight
                    * last_move_prob 
                    * math.sqrt(total_visits) / (1 + self.N[n]))

        return max(self.children[node], key=puct)


class Node(ABC):
    """
    A representation of a single board state.
    MCTS works by constructing a tree of these Nodes.
    Could be e.g. a chess or checkers board state.
    """

    @abstractmethod
    def find_children(self):
        "All possible successors of this board state"
        return set()

    @abstractmethod
    def find_random_child(self):
        "Random successor of this board state (for more efficient simulation)"
        return None

    @abstractmethod
    def is_terminal(self):
        "Returns True if the node has no children"
        return True

    @abstractmethod
    def reward(self):
        "Assumes `self` is terminal node. 1=win, 0=loss, .5=tie, etc"
        return 0

    @abstractmethod
    def __hash__(self):
        "Nodes must be hashable"
        return 123456789

    @abstractmethod
    def __eq__(self, other):
        "Nodes must be comparable"
        return True