from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class Node:
    name: str | None
    children: list["Node"]
    x: float | None = None
    y: float | None = None
    node_id: int | None = None


def _tokenize_newick(text: str) -> Iterator[str]:
    buf = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "'":
            i += 1
            start = i
            while i < len(text) and text[i] != "'":
                i += 1
            yield text[start:i]
            i += 1
            continue
        if ch in "(),:;":
            if buf:
                yield "".join(buf)
                buf = []
            yield ch
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        yield "".join(buf)


def parse_newick(text: str) -> Node | None:
    tokens = list(_tokenize_newick(text))
    if not tokens:
        return None
    if ";" in tokens:
        tokens = tokens[: tokens.index(";")]
    idx = 0

    def next_token() -> str | None:
        nonlocal idx
        if idx >= len(tokens):
            return None
        tok = tokens[idx]
        idx += 1
        return tok

    def peek() -> str | None:
        if idx >= len(tokens):
            return None
        return tokens[idx]

    def parse_subtree() -> Node:
        tok = next_token()
        if tok is None:
            raise ValueError("Invalid Newick: unexpected end")
        if tok == "(":
            children = [parse_subtree()]
            while peek() == ",":
                next_token()
                children.append(parse_subtree())
            close_tok = next_token()
            if close_tok != ")":
                raise ValueError("Invalid Newick: missing closing paren")
            name = None
            if peek() not in (None, ",", ")", ":", ";"):
                name = next_token()
            node = Node(name=name, children=children)
        else:
            node = Node(name=tok, children=[])

        if peek() == ":":
            next_token()
            if peek() not in (None, ",", ")", ";"):
                _ = next_token()
        return node

    root = parse_subtree()
    return root


def try_parse_newick(text: str) -> Node | None:
    try:
        if not text or not text.strip():
            return None
        return parse_newick(text)
    except ValueError:
        return None


def layout_tree(root: Node):
    import pandas as pd

    nodes: list[Node] = []
    edges = []
    next_leaf_x = 0

    def assign_positions(node: Node, depth: int) -> None:
        nonlocal next_leaf_x
        node.y = depth
        if not node.children:
            node.x = float(next_leaf_x)
            next_leaf_x += 1
        else:
            for child in node.children:
                assign_positions(child, depth + 1)
            node.x = sum(child.x for child in node.children if child.x is not None) / len(
                node.children
            )
        node.node_id = len(nodes)
        nodes.append(node)

    assign_positions(root, 0)

    for node in nodes:
        for child in node.children:
            edges.append(
                {
                    "parent_id": node.node_id,
                    "child_id": child.node_id,
                    "x": node.x,
                    "y": node.y,
                    "x2": child.x,
                    "y2": child.y,
                }
            )

    nodes_df = pd.DataFrame(
        [
            {
                "node_id": n.node_id,
                "name": n.name or "",
                "x": n.x,
                "y": n.y,
                "is_leaf": len(n.children) == 0,
            }
            for n in nodes
        ]
    )
    edges_df = pd.DataFrame(edges)
    return nodes_df, edges_df
