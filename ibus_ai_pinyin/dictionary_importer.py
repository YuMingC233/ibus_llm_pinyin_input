import hashlib
import json
import os

from ibus_ai_pinyin.dictionary_format import normalize_dictionary


class DictionaryImporter:
    def __init__(self, store):
        self.store = store

    def load_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def import_file(self, path, mode="merge", dry_run=False):
        data = self.load_file(path)
        dictionary, errors, warnings = normalize_dictionary(data)
        report = {
            "dictionary_name": dictionary["name"] if dictionary else data.get("name", ""),
            "total_entries": len(data.get("entries", [])) if isinstance(data, dict) else 0,
            "valid_entries": len(dictionary["entries"]) if dictionary else 0,
            "skipped_entries": dictionary.get("skipped_entries", 0) if dictionary else 0,
            "inserted_terms": 0,
            "updated_terms": 0,
            "inserted_pinyin": 0,
            "inserted_aliases": 0,
            "inserted_tags": 0,
            "warnings": warnings,
            "errors": errors,
            "dry_run": dry_run,
        }
        if errors or dry_run:
            return report

        store_report = self.store.import_dictionary(
            dictionary,
            file_path=os.path.abspath(path),
            file_hash=self._file_hash(path),
            mode=mode,
        )
        report.update(store_report)
        report["warnings"] = warnings
        report["errors"] = []
        return report

    def _file_hash(self, path):
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
