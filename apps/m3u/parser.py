import re
import os
import gzip
import zipfile
import logging
import io
from typing import Generator, Dict, Any, Optional
from .utils import normalize_stream_url

logger = logging.getLogger(__name__)

def get_case_insensitive_attr(attributes, key, default=""):
    """Get attribute value using case-insensitive key lookup."""
    for attr_key, attr_value in attributes.items():
        if attr_key.lower() == key.lower():
            return attr_value
    return default

def parse_extinf_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse an EXTINF line from an M3U file.
    This function removes the "#EXTINF:" prefix, then extracts all key="value" attributes,
    and treats everything after the last attribute as the display name.

    Returns a dictionary with:
      - 'attributes': a dict of attribute key/value pairs (e.g. tvg-id, tvg-logo, group-title)
      - 'display_name': the text after the attributes (the fallback display name)
      - 'name': the value from tvg-name (if present) or the display name otherwise.
    """
    if not line.startswith("#EXTINF:"):
        return None
    content = line[len("#EXTINF:") :].strip()

    # Single pass: extract all attributes AND track the last attribute position
    # This regex matches both key="value" and key='value' patterns
    attrs = {}
    last_attr_end = 0

    # Use a single regex that handles both quote types
    for match in re.finditer(r'([^\s]+)=(["\'])([^\2]*?)\2', content):
        key = match.group(1)
        value = match.group(3)
        attrs[key] = value
        last_attr_end = match.end()

    # Everything after the last attribute (skipping leading comma and whitespace) is the display name
    if last_attr_end > 0:
        remaining = content[last_attr_end:].strip()
        # Remove leading comma if present
        if remaining.startswith(','):
            remaining = remaining[1:].strip()
        display_name = remaining
    else:
        # No attributes found, try the old comma-split method as fallback
        parts = content.split(',', 1)
        if len(parts) == 2:
            display_name = parts[1].strip()
        else:
            display_name = content.strip()

    # Use tvg-name attribute if available; otherwise try tvc-guide-title, then fall back to display name.
    name = get_case_insensitive_attr(attrs, "tvg-name", None)
    if not name:
        name = get_case_insensitive_attr(attrs, "tvc-guide-title", None)
    if not name:
        name = display_name
    return {"attributes": attrs, "display_name": display_name, "name": name}

class M3UParser:
    """
    Efficient, generator-based parser for M3U files.
    Avoids loading the entire file into memory.
    """

    @staticmethod
    def _open_file(file_path: str):
        """Helper to open regular, gzip, or zip files as a text stream."""
        if file_path.endswith(".gz"):
            return gzip.open(file_path, "rt", encoding="utf-8", errors='ignore')
        elif file_path.endswith(".zip"):
            z = zipfile.ZipFile(file_path, "r")
            # Find first m3u file
            for name in z.namelist():
                if name.endswith(".m3u") or name.endswith(".m3u8"):
                    return io.TextIOWrapper(z.open(name), encoding="utf-8", errors='ignore')
            # If no m3u found, maybe the zip itself is the content? Unlikely.
            raise ValueError(f"No M3U file found in zip: {file_path}")
        else:
            return open(file_path, "r", encoding="utf-8", errors='ignore')

    @classmethod
    def parse_file(cls, file_path: str) -> Generator[Dict[str, Any], None, None]:
        """
        Yields parsed stream dictionaries from an M3U file.
        Each yielded item contains the 'url' and parsed EXTINF attributes.
        """
        if not os.path.exists(file_path):
            logger.error(f"M3U file not found: {file_path}")
            return

        current_entry = {}

        try:
            with cls._open_file(file_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("#EXTINF:"):
                        parsed = parse_extinf_line(line)
                        if parsed:
                            current_entry = parsed
                    elif line.startswith("#"):
                        # Other directives (EXTGRP, etc) - can be supported later
                        continue
                    elif line.startswith("http") or line.startswith("rtsp") or line.startswith("rtp") or line.startswith("udp"):
                        # Assume it's a URL if we have a pending entry
                        if current_entry:
                            # Normalize URL
                            url = normalize_stream_url(line) if line.startswith("udp") else line
                            current_entry['url'] = url
                            yield current_entry
                            current_entry = {}
        except Exception as e:
            logger.error(f"Error parsing M3U file {file_path}: {e}")

    @classmethod
    def extract_groups(cls, file_path: str) -> Dict[str, Dict]:
        """
        Scans the file specifically to extract unique groups.
        Returns a dictionary of group_name -> custom_properties (empty dict for now).
        """
        groups = {"Default Group": {}}

        if not os.path.exists(file_path):
            return groups

        try:
            with cls._open_file(file_path) as f:
                for line in f:
                    if line.startswith("#EXTINF:"):
                        # Minimal parsing to find group-title
                        parsed = parse_extinf_line(line.strip())
                        if parsed:
                            group_name = get_case_insensitive_attr(parsed["attributes"], "group-title", "")
                            if group_name and group_name not in groups:
                                groups[group_name] = {}
        except Exception as e:
            logger.error(f"Error extracting groups from {file_path}: {e}")

        return groups
