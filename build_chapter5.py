"""Generate preparation/execution LaTeX from a saved CIM status directory."""
import argparse
import json
from pathlib import Path

def esc(value):
    chars = {'\\': r'\textbackslash{}', '_': r'\_', '%': r'\%', '&': r'\&', '#': r'\#',
             '$': r'\$', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(chars.get(c, c) for c in str(value))

def build(root):
    root = Path(root)
    ready = json.loads((root / 'readiness.json').read_text(encoding='utf-8'))
    rows = json.loads((root / 'execution_table.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / 'run_manifest.json').read_text(encoding='utf-8'))
    attempted = sum(r['provider_attempts'] > 0 for r in rows)
    terminal = sum(r['terminal_prediction'] for r in rows)
    processed = sum(r['successfully_processed'] for r in rows)
    counts = [('Proposed episodes', len(ready)), ('Selected episodes', sum(r['selected'] for r in ready)),
              ('Input and selection ready', sum(r['input_and_selection_ready'] for r in ready)),
              ('Execution eligible for current configuration', sum(r['model_execution_eligible'] for r in ready)),
              ('Cases with provider attempts', attempted), ('Terminal predictions', terminal),
              ('Successfully processed cases', processed),
              ('Processing failures', sum(r['processing_failure'] for r in rows)),
              ('Transport failures', sum(r['transport_failures'] for r in rows)),
              ('Complete assisted r1 records', sum(r['r1_complete'] for r in ready)),
              ('Complete r2 records', sum(r['r2_complete'] for r in ready)),
              ('Final reference eligible', sum(r['final_scoring_eligible'] for r in ready)),
              ('Reviewed model evidence chains', 0),
              ('Provisional source group identifiers', len({r['source_cluster'] for r in ready}))]
    table = '\\begin{table}[htbp]\n\\centering\n\\begin{tabular}{lr}\n\\hline\nMeasure & Count \\\\\n\\hline\n'
    table += ''.join(esc(k) + ' & ' + str(v) + ' \\\\\n' for k, v in counts)
    table += '\\hline\n\\end{tabular}\n\\caption{Consequential Interpretation Mismatch (CIM): preparation and execution status.}\n\\end{table}\n'
    (root / 'chapter5_tables.tex').write_text(table, encoding='utf-8')
    prose = (r'\subsection{Preparation and execution status}' + '\n'
             + f'This saved condition contains {len(ready)} selected episodes; {attempted} received a provider attempt, '
             + f'{terminal} have terminal predictions and {processed} were successfully processed. '
             + 'Coverage uses all selected episodes as its denominator. A blocked case is not a model processing failure.\n\n'
             + 'Context verification rests on the recorded user attestation in the assisted-development pilot. '
             + 'Source groups are provisional identifiers; shared maps and potentially shared game sessions prevent an independence claim. '
             + 'Overlapping admitted source-turn windows are recorded separately in source\\_dependence.json.\n\n'
             + 'No completed adjudicated references are available. Accuracy, confusion-table results, false warnings on ALIGNED, '
             + 'warnings on UNRESOLVED and evidence-chain correctness are unavailable. Mismatch sensitivity is undefined '
             + 'without positive adjudicated mismatch cases. Versions of r1 are one reader; no inter-reader reliability is estimated.\n\n'
             + 'Software transport checks use test-only mock responses and are not empirical model results. '
             + 'No genuine engineering-fixture execution is included. No baselines, ablations, superiority or warning lead time were measured. '
             + 'The implemented method is staged strict Tier S. Later corrected prefixes cannot establish earlier warning.\n')
    (root / 'chapter5_results.tex').write_text(prose, encoding='utf-8')
    return dict(counts)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('results_directory')
    print(json.dumps(build(p.parse_args().results_directory), indent=2))
