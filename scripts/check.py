#!/usr/bin/env python3
"""One fail-closed entry point for local and hosted workflow checks."""
import pathlib
import os
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkflowLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key, value in node.value:
        key = loader.construct_object(key, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value, deep=deep)
    return result


WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def validate(directory):
    errors = []
    files = sorted(set(directory.glob('*.yml')) | set(directory.glob('*.yaml')))
    if not files:
        return ['No workflow files found']
    for path in files:
        try:
            workflow = yaml.load(path.read_text(), Loader=WorkflowLoader)
            if not isinstance(workflow, dict) or not workflow.get('jobs'):
                raise ValueError('Workflow must be a nonempty mapping with jobs')
            triggers = workflow.get('on', workflow.get(True))
            if not triggers:
                raise ValueError('Workflow must declare triggers')
            call = triggers.get('workflow_call') if isinstance(triggers, dict) else None
            if call is not None:
                for name, spec in call.get('inputs', {}).items():
                    if spec.get('type') not in {'string', 'boolean', 'number'}:
                        raise ValueError('Invalid type for input ' + name)
            for job_name, job in workflow['jobs'].items():
                if 'uses' not in job and ('timeout-minutes' not in job or not (job.get('permissions') or workflow.get('permissions'))):
                    raise ValueError(job_name + ': explicit timeout and permissions required')
                uses = [job['uses']] if 'uses' in job else []
                for step in job.get('steps', []):
                    if 'uses' in step:
                        uses.append(step['uses'])
                    if step.get('uses', '').startswith('actions/checkout@') and step.get('with', {}).get('persist-credentials') is not False:
                        raise ValueError(job_name + ': checkout must not persist credentials')
                    if 'run' in step and '${{' in step['run']:
                        raise ValueError(job_name + ': pass expressions through env, not run source')
                for use in uses:
                    if use.startswith('./') or use.startswith('$/'):
                        continue
                    if use.startswith('docker://'):
                        valid = re.fullmatch(r'docker://[^@]+@sha256:[0-9a-f]{64}', use)
                    else:
                        valid = re.fullmatch(r'[^@]+@[0-9a-f]{40}', use)
                    if not valid:
                        raise ValueError(job_name + ': unpinned uses: ' + use)
        except (ValueError, TypeError, AttributeError, yaml.YAMLError) as error:
            errors.append(f'{path}: {error}')
    return errors


def main():
    errors = validate(ROOT / '.github/workflows')
    if errors:
        raise SystemExit('\n'.join(errors))
    commands = [
        ['actionlint'],
        ['zizmor', '--offline', '.github/workflows'],
        [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', '*_test.py'],
        [sys.executable, '-B', 'scripts/reference.py', '--check'],
    ]
    environment = dict(os.environ)
    environment['PATH'] = str(pathlib.Path(sys.executable).parent) + os.pathsep + environment['PATH']
    for command in commands:
        print('Running ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, env=environment, check=True)
    print('All workflow checks passed.')


if __name__ == '__main__':
    main()
