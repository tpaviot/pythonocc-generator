#!/usr/bin/env python3

##Copyright 2008-2026 Thomas Paviot (tpaviot@gmail.com)

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

import argparse
import json
import re
from pathlib import Path


def read_packages(toolkit):
    """The packages of the toolkit directory, None if they are not listed.

    OCCT 7 lists them in a PACKAGES file, one per line. OCCT 8 in a
    PACKAGES.cmake file:
        set(OCCT_TKernel_LIST_OF_PACKAGES
          FSD
          ...
        )
    """
    packages_file = toolkit / "PACKAGES"
    if packages_file.is_file():
        lines = packages_file.read_text(encoding="utf8").splitlines()
        return [line.strip() for line in lines if line.strip()]
    packages_file = toolkit / "PACKAGES.cmake"
    if packages_file.is_file():
        content = packages_file.read_text(encoding="utf8")
        match = re.search(
            rf"set\(\s*OCCT_{re.escape(toolkit.name)}_LIST_OF_PACKAGES\b([^)]*)\)",
            content,
        )
        if match:
            # the comments of the list are dropped, a package of another
            # toolkit is given by its path (TKOpenGles: ../TKOpenGl/OpenGl)
            items = re.sub(r"#[^\n]*", "", match.group(1)).split()
            return [Path(item).name for item in items]
    return None


def process_toolkits(occt_directory):
    """Process OCCT toolkits and generate JSON output."""
    # Verify the directory exists
    if not Path(occt_directory).is_dir():
        raise ValueError(f"Directory does not exist: {occt_directory}")

    occt_src_path = Path(occt_directory) / "src"
    if not occt_src_path.is_dir():
        raise ValueError(f"Source directory not found: {occt_src_path}")

    toolkits = {}

    # the TK folders are in src (OCCT 7) or in src/<module> (OCCT 8, e.g.
    # src/FoundationClasses/TKernel)
    toolkit_dirs = [*occt_src_path.glob("TK*"), *occt_src_path.glob("*/TK*")]
    for toolkit in sorted(toolkit_dirs, key=lambda path: path.name):
        if not toolkit.is_dir():
            continue
        packages = read_packages(toolkit)
        if packages is None:
            print(f"Warning: no PACKAGES file found in {toolkit}")
            continue
        # alphabetical sort
        toolkits[toolkit.name] = sorted(packages)

    return toolkits


def main():
    parser = argparse.ArgumentParser(
        description="Process OCCT toolkits and generate a JSON file containing package information."
    )
    parser.add_argument(
        "occt_directory",
        help="Path to the OCCT source directory (e.g., /path/to/OCCT-8_0_1/)",
    )
    parser.add_argument(
        "--output",
        default="toolkits.json",
        help="Output JSON file path (default: toolkits.json)",
    )

    args = parser.parse_args()

    toolkits = process_toolkits(args.occt_directory)

    # save to json
    with Path(args.output).open("w", encoding="utf8") as f:
        json.dump(toolkits, f, indent=4, ensure_ascii=False)

    print(f"Successfully wrote toolkit information to {args.output}")
    print(f"Processed {len(toolkits)} toolkits")


if __name__ == "__main__":
    main()
