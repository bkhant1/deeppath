"""
Support some XPath-like syntax for accessing nested structures
"""

from typing import Sequence, MutableSequence, Mapping
from collections import namedtuple
import re


def _flatdget(data, key):
    if not isinstance(data, Sequence) or isinstance(key, int):
        return data[key]
    return [_flatdget(value, key) for value in data]


_REPETITION_REGEX = re.compile(r"([\w\*]+)\[([\d-]+)\]")


def _get_repetition_index(key):
    """Try to match a path for a repetition.
    This will return the key and the repetition index or None if the key
    does not match the expected regex"""
    match = _REPETITION_REGEX.search(key)
    if match:
        key = match.group(1)
        repetition_number = match.group(2)
        return key, int(repetition_number)


ThroughListFlat = namedtuple("ThroughListFlat", [])
ThroughListIndexed = namedtuple("ThroughListIndexed", ['index'])
ThroughDictFlat = namedtuple("ThroughDictFlat", [])
ThroughDictKey = namedtuple("ThroughDictKey", ['key'])


def make_command(str_token):
    if str_token == "*":
        return ThroughDictFlat()
    elif str_token == "[*]":
        return ThroughListFlat()
    else:
        match_list_index = re.match(r"\[(-?\d+)\]", str_token)
        if match_list_index:
            return ThroughListIndexed(int(match_list_index.group(1)))
        else:
            return ThroughDictKey(str_token)


def read_path(path):
    if path[0] == "/":
        path = path[1:]
    path_commands = re.sub(r"([^/])(\[(?:\*|-?\d+)\])", r"\g<1>/\g<2>", path).split("/")
    return list(map(make_command, path_commands))


def go_through_dict_key(key, list_of_items):
    result = []
    for item in list_of_items:
        if isinstance(item, Mapping) and key in item:
            result.append(item[key])
    return result


def go_through_list_index(index, list_of_items):
    result = []
    for item in list_of_items:
        if isinstance(item, Sequence) and len(item) > index:
            result.append(item[index])
    return result


def go_through_list_flat(list_of_items):
    result = []
    for item in list_of_items:
        if isinstance(item, Sequence):
            result += [x for x in item]
    return result


def go_through_dict_flat(list_of_items):
    result = []
    for item in list_of_items:
        if isinstance(item, Mapping):
            result += [x for x in item.values()]
    return result


def dget(data, path, default=None):

    def process_commands(commands, data):
        if not commands:
            return data
        else:
            next_command = commands[0]
            if isinstance(next_command, ThroughDictKey):
                return process_commands(
                    commands[1:],
                    go_through_dict_key(next_command.key, data)
                )
            elif isinstance(next_command, ThroughListIndexed):
                return process_commands(
                    commands[1:],
                    go_through_list_index(next_command.index, data)
                )
            elif isinstance(next_command, ThroughListFlat):
                return process_commands(
                    commands[1:],
                    go_through_list_flat(data)
                )
            elif isinstance(next_command, ThroughDictFlat):
                return process_commands(
                    commands[1:],
                    go_through_dict_flat(data)
                )
            else:
                return []

    commands = read_path(path)
    result_list = process_commands(commands, [data])

    if len(result_list) == 0:
        return default
    elif not ThroughListFlat() in commands and not ThroughDictFlat() in commands:
        return result_list[0]
    else:
        return result_list


def dget2(data, path, default=None):
    """
    Gets a deeply nested value in a dictionary.
    Returns default if provided when any key doesn't match.
    """
    if path.startswith("/"):
        path = path[1:]
    try:
        for key in path.split("/"):
            repetition = _get_repetition_index(key)
            if repetition:
                key, index = repetition
                if key != "*":
                    data = _flatdget(data, key)
                    data = _flatdget(data, index)
                else:
                    data = [_flatdget(value, index) for value in data.values()]
            else:
                if key != "*":
                    data = _flatdget(data, key)
                else:
                    if not isinstance(data, Sequence):
                        data = [value for value in data.values()]
    except (KeyError, TypeError, IndexError):
        return default
    return data


def dset(data, path, value):
    """Set a key in a deeply nested structure"""
    if path.startswith("/"):
        path = path[1:]
    for key in path.split("/")[:-1]:
        subpath = _get_repetition_index(key)
        if not subpath:
            if key not in data:
                data[key] = {}
            data = data[key]
        else:
            key, index = subpath
            if key not in data:
                data[key] = [{}]
            elif len(data[key]) == index:
                data[key].append({})
            data = data[key][index]

    last = _get_repetition_index(path.split("/")[-1])
    if not last:
        data[path.split("/")[-1]] = value
    else:
        key, index = last
        if key not in data:
            data[key] = [value]
        else:
            if len(data[key]) == index:
                data[key].append(value)
            else:
                data[key][index] = value


def _dwalk_with_path(data, path):
    if isinstance(data, Mapping):
        for key, value in data.items():
            subpath = path + [key]
            yield from _dwalk_with_path(value, subpath)
    elif isinstance(data, MutableSequence):
        for index, value in enumerate(data):
            subpath = path[:]
            subpath[-1] = subpath[-1] + f"[{index}]"
            yield from _dwalk_with_path(value, subpath)
    else:
        yield "/".join(path), data


def dwalk(data):
    """Generator that will yield values for each path to a leaf of a nested structure"""
    yield from _dwalk_with_path(data, [])
