"""Safety and provenance fixtures. Temporary review labels are not research results."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from prospective.build_candidates import ROOT, build_records
from prospective.draft_map_inventories import build as build_maps
from prospective.validate_candidates import validate


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class SafeRegenerationTests(unittest.TestCase):
    def test_nonempty_destination_preserves_existing_reviews(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / 'work'
            destination.mkdir()
            review = destination / 'REVIEWS.json'
            review.write_text('{"reviewer_id":"keep-my-work"}\n')
            before = snapshot(destination)
            with self.assertRaisesRegex(ValueError, 'new or empty'):
                build_records(destination)
            self.assertEqual(snapshot(destination), before)
            with self.assertRaisesRegex(ValueError, 'outside'):
                build_records(ROOT / 'would_replace_source')

    def test_new_regeneration_does_not_reset_source_reviews_or_context(self):
        with tempfile.TemporaryDirectory() as td:
            source_package = Path(td) / 'existing'
            source = source_package / 'prospective'
            source.mkdir(parents=True)
            for name in ['source_transcripts', 'source_maps', 'provenance']:
                shutil.copytree(ROOT / name, source / name)
            shutil.copy2(ROOT / 'selection_specs.json', source / 'selection_specs.json')
            (source_package / 'context').mkdir()
            shutil.copy2(ROOT.parent / 'context/m9_inventory_DRAFT.json',
                         source_package / 'context/m9_inventory_DRAFT.json')
            (source / 'context_drafts').mkdir()
            write_json(source / 'context_drafts/m3_DRAFT.json', {'review_status': 'verified', 'reviewer': 'reader-fixture'})
            write_json(source_package / 'REVIEWS.json', {'reviewer_id': 'reader-fixture', 'notes': 'Preserve this review.'})
            (source_package / 'pilot_selection.csv').write_text('preserved selection fixture\n')
            before = snapshot(source_package)
            destination = Path(td) / 'fresh'
            result = build_records(destination, source)
            self.assertEqual(snapshot(source_package), before)
            self.assertTrue(result['existing_reviews_preserved'])
            audit = validate(destination / 'prospective', baseline=True)
            self.assertEqual(audit['source_blob_hashes_matching'], 20)
            self.assertEqual(audit['selected_declared_in_register'], 0)

    def test_map_builder_checks_entire_batch_before_writing(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            source = package / 'prospective'
            out = source / 'context_drafts'
            out.mkdir(parents=True)
            (package / 'context').mkdir()
            shutil.copy2(ROOT.parent / 'context/m9_inventory_DRAFT.json',
                         package / 'context/m9_inventory_DRAFT.json')
            changed = out / 'm6_DRAFT.json'
            write_json(changed, {'review_status': 'verified', 'notes': 'Keep reviewed map.'})
            before = snapshot(out)
            with self.assertRaisesRegex(ValueError, 'changed or reviewed inventory'):
                build_maps(source)
            self.assertEqual(snapshot(out), before)
            self.assertFalse((out / 'm3_DRAFT.json').exists())

    def test_reviewed_selected_state_passes_default_but_not_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td) / 'fresh'
            build_records(package)
            root = package / 'prospective'
            sid = 'MT03_q1ec4_r019'
            record_path = root / 'curator_cases' / (sid + '.json')
            record = json.loads(record_path.read_text(encoding='utf-8'))
            record['study_role'] = 'pilot'
            record['selection_metadata']['selection_status'] = 'human_selected'
            record['manual_annotation'] = {'fixture_only': True}
            record['annotation_review']['review_status'] = 'adjudicated'
            record['annotation_review']['adjudicated_label'] = 'UNRESOLVED'
            for context in record['observer_input']['context_sources']:
                context['adapter']['review_status'] = 'verified'
            write_json(record_path, record)
            write_json(root / 'observer_inputs' / (sid + '.json'), record['observer_input'])
            write_json(root / 'observer_cases' / (sid + '.json'), {
                'sample_id': sid, 'study_role': 'pilot', 'observer_input': record['observer_input']})
            register_path = package / 'pilot_selection.csv'
            with register_path.open(newline='') as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                if row['sample_id'] == sid:
                    row['selected'] = 'true'
            with register_path.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = validate(root)
            self.assertEqual(result['selected_declared_in_register'], 1)
            self.assertEqual(result['reference_labels_adjudicated_declared'], 1)
            self.assertEqual(result['context_preflight_passed'], 1)
            self.assertEqual(result['unverified_contexts_block_model_run'], 19)
            self.assertNotIn('measured_model_runs', result)
            with self.assertRaisesRegex(ValueError, 'baseline'):
                validate(root, baseline=True)

    def test_default_validation_still_detects_changed_source_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td) / 'fresh'
            build_records(package)
            root = package / 'prospective'
            source = root / 'source_transcripts/q1ec4.txt'
            source.write_bytes(source.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                validate(root)

    def test_cli_prints_without_overwriting_archived_validation(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td) / 'fresh'
            build_records(package)
            root = package / 'prospective'
            archive = root / 'validation.json'
            archive.write_text('{"archive":"preserve"}\n')
            before = archive.read_bytes()
            command = [sys.executable, str(ROOT / 'validate_candidates.py'), '--root', str(root)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['validation'], 'passed')
            self.assertEqual(archive.read_bytes(), before)
            rejected = subprocess.run(command + ['--out', str(archive)], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('Refusing to overwrite', rejected.stderr)
            self.assertEqual(archive.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
