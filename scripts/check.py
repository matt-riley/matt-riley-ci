#!/usr/bin/env python3
"""One fail-closed entry point for local and hosted workflow checks."""
import pathlib
import os
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
# GitHub's reusable-workflow caller schema; environment belongs inside the callee.
# https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#supported-keywords-for-jobs-that-call-a-reusable-workflow
# cache-mode is explicitly supported by the current caller schema.
CALL_JOB_KEYS = {'name', 'uses', 'with', 'secrets', 'strategy', 'needs', 'if', 'concurrency', 'permissions', 'cache-mode'}
# actionlint 1.7.12 predates GitHub's queue property. Only suppress its unknown-key
# diagnostic; validate literal queue values and max/cancellation semantics ourselves.
QUEUE_COMPAT = r'^unexpected key "queue" for "concurrency" section\.'


def validate_queue(value):
    if not isinstance(value, dict) or 'queue' not in value:
        return
    if value['queue'] not in ('single', 'max'):
        raise ValueError('Concurrency queue must be single or max')
    if value['queue'] == 'max' and value.get('cancel-in-progress', False) is not False:
        raise ValueError('queue:max requires cancel-in-progress to be false or omitted')


class WorkflowLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key, value in node.value:
        if key.tag == 'tag:yaml.org,2002:merge':
            raise ValueError('YAML merge keys are outside this workflow policy; use anchors and aliases')
        key = loader.construct_object(key, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value, deep=deep)
    return result


WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def call_permissions(path, seen=None):
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError('Recursive local workflow call: ' + str(path))
    seen = seen | {path}
    target = yaml.load(path.read_text(), Loader=WorkflowLoader)
    levels = {'none': 0, 'read': 1, 'write': 2}
    required = {}
    for job in target['jobs'].values():
        declared = job.get('permissions', target.get('permissions', {}))
        if not isinstance(declared, dict):
            raise ValueError('Local callable workflows must declare permission mappings')
        for key, level in declared.items():
            required[key] = max(required.get(key, 0), levels[level])
        use = job.get('uses', '')
        if use.startswith(('./', '$/')):
            for key, level in call_permissions(path.parent / pathlib.Path(use[2:]).name, seen).items():
                required[key] = max(required.get(key, 0), level)
    return required


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
            validate_queue(workflow.get('concurrency'))
            call = triggers.get('workflow_call') if isinstance(triggers, dict) else None
            if call is not None:
                for name, spec in call.get('inputs', {}).items():
                    if spec.get('type') not in {'string', 'boolean', 'number'}:
                        raise ValueError('Invalid type for input ' + name)
            for job_name, job in workflow['jobs'].items():
                validate_queue(job.get('concurrency'))
                if 'uses' not in job and ('timeout-minutes' not in job or not (job.get('permissions') or workflow.get('permissions'))):
                    raise ValueError(job_name + ': explicit timeout and permissions required')
                use = job.get('uses', '')
                if use and set(job) - CALL_JOB_KEYS:
                    raise ValueError(job_name + ': unsupported reusable caller keys: ' + ', '.join(sorted(set(job) - CALL_JOB_KEYS)))
                if use.startswith(('./', '$/')):
                    target = directory / pathlib.Path(use[2:]).name
                    if not target.is_file():
                        raise ValueError(job_name + ': missing local workflow: ' + use)
                    callee = yaml.load(target.read_text(), Loader=WorkflowLoader)
                    events = callee.get('on', callee.get(True, {}))
                    if not isinstance(events, dict) or 'workflow_call' not in events:
                        raise ValueError(job_name + ': target must support workflow_call')
                    definitions = (events['workflow_call'] or {}).get('inputs', {})
                    supplied = job.get('with', {})
                    if set(supplied) - set(definitions):
                        raise ValueError(job_name + ': unknown reusable workflow input')
                    for name, spec in definitions.items():
                        if spec.get('required') and name not in supplied:
                            raise ValueError(job_name + ': missing required input ' + name)
                        if name not in supplied or '${{' in str(supplied[name]):
                            continue
                        value = supplied[name]
                        valid = {'string': isinstance(value, str), 'boolean': isinstance(value, bool), 'number': isinstance(value, (int, float)) and not isinstance(value, bool)}
                        if not valid.get(spec['type'], False):
                            raise ValueError(job_name + ': invalid input type for ' + name)
                    granted = job.get('permissions', workflow.get('permissions', {}))
                    if not isinstance(granted, dict):
                        raise ValueError(job_name + ': local callers require scoped permission mappings')
                    levels = {'none': 0, 'read': 1, 'write': 2}
                    for key, minimum in call_permissions(target).items():
                        if levels.get(granted.get(key, 'none'), 0) < minimum:
                            raise ValueError(job_name + ': caller must grant ' + key + ' to ' + use)
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
        except (ValueError, TypeError, AttributeError, yaml.YAMLError, OSError, KeyError) as error:
            errors.append(f'{path}: {error}')
    return errors


def main():
    errors = validate(ROOT / '.github/workflows')
    if errors:
        raise SystemExit('\n'.join(errors))
    commands = [
        ['actionlint', '-ignore', QUEUE_COMPAT],
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
