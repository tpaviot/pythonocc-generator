#!/usr/bin/env python3

##Copyright 2008-2024 Thomas Paviot (tpaviot@gmail.com)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import glob
import argparse
import sys


def process_toolkits(occt_directory):
    """Process OCCT toolkits and generate JSON output."""
    # Verify the directory exists
    if not os.path.isdir(occt_directory):
        raise ValueError(f"Directory does not exist: {occt_directory}")

    occt_src_path = os.path.join(occt_directory, "src")
    if not os.path.isdir(occt_src_path):
        raise ValueError(f"Source directory not found: {occt_src_path}")

    # load all TK folders
    all_toolkits = glob.glob(os.path.join(occt_src_path, "TK*"))
    toolkits = {}

    # loop over toolkits
    for toolkit in all_toolkits:
        toolkit_name = toolkit.split(os.sep)[-1]
        packages_file = os.path.join(toolkit, "PACKAGES")

        if not os.path.exists(packages_file):
            print(f"Warning: PACKAGES file not found in {toolkit}")
            continue

        with open(packages_file, "r") as f:
            packages = [l.strip() for l in f.readlines()]

        # alphabetical sort
        packages.sort()
        # add the entry to the dict
        toolkits[toolkit_name] = packages

    return toolkits


def main():
    parser = argparse.ArgumentParser(
        description="Process OCCT toolkits and generate a JSON file containing package information."
    )
    parser.add_argument(
        "occt_directory",
        help="Path to the OCCT directory (e.g., /path/to/OCCT-7_8_1/)",
    )
    parser.add_argument(
        "--output",
        default="toolkits.json",
        help="Output JSON file path (default: toolkits.json)",
    )

    args = parser.parse_args()

    toolkits = process_toolkits(args.occt_directory)

    # save to json
    with open(args.output, "w", encoding="utf8") as f:
        json.dump(toolkits, f, indent=4, ensure_ascii=False)

    print(f"Successfully wrote toolkit information to {args.output}")
    print(f"Processed {len(toolkits)} toolkits")


if __name__ == "__main__":
    main()
