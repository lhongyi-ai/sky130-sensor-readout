"""Static API inventory + native audit regression; does not emulate Cadence."""
import json
import re

from test_pulse_cdf_v1 import BASE, main as check_pulse_inputs

# Documented SKILL forms/builtins and the small API set reviewed for this file.
# The database/CDF/save APIs also occur in the already-executed basic generator.
BUILTINS = set('''when boundp if printf error strcat getShellEnvVar list procedure
car setof let and stringp strlen numberp abs max unless length cadr foreach
caddr fprintf drain or outfile errset close'''.split())
CADENCE_APIS = set('''dbClose cdfParseFloatString cdfGetInstCDF cdfFindParamByName
ddGetObj dbOpenCellViewByType dbReplaceProp schCheck dbSave'''.split())


def check_calls(script):
    code = re.sub(r'"(?:\\.|[^"\\])*"|;[^\n]*', ' ', script)
    procedures = set(re.findall(r'procedure\s*\(\s*(\w+)\s*\(', code))
    calls = set(re.findall(r'\b([A-Za-z]\w*)\s*\(', code))
    unknown = calls - BUILTINS - CADENCE_APIS - procedures
    if unknown:
        raise ValueError('Unreviewed SKILL calls: ' + ', '.join(sorted(unknown)))
    return sorted(calls & CADENCE_APIS)


def main():
    source = BASE / 'releases/p1_fix_pulses_v2.il'
    script = source.read_text()
    apis = check_calls(script)
    # The actual v1 API failure must be detected by this new check.
    old = (BASE / 'releases/p1_fix_pulses_v1.il').read_text()
    try:
        check_calls(old)
    except ValueError as error:
        assert 'dbFindPropByName' in str(error)
    else:
        raise AssertionError('The failed v1 lookup must be rejected')
    check_pulse_inputs('v2')
    output = source.with_suffix('.validation.json')
    report = json.loads(output.read_text())
    report['checks'] += [
        'Reviewed direct function-call inventory; actual v1 undefined call rejected',
        'Source review: stale read references closed; editable references preserved',
    ]
    report['reviewed_cadence_api_calls'] = apis
    report['remaining_validation'] = [
        'Run v2 in school Virtuoso; local checks do not execute SKILL',
        'Regenerate native RC and OTA step netlists and run simulations',
    ]
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
