#!/usr/bin/env python

# Copyright (C) 2011-2013 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import os.path
import re
import shutil
import sys
import urllib2

from common import run_local

URL = ('https://git.openstack.org/cgit/openstack-infra/project-config/'
       'plain/gerrit/projects.yaml')
PROJECT_RE = re.compile('^-?\s+project:\s+(.*)$')

override_mappings = {
    "openstack-infra/devstack-gate" : "tesora/tesora-devstack-gate",
    "openstack-infra/nodepool" : "tesora/tesora-nodepool",
    "openstack-infra/project-config" : "tesora/tesora-project-config",
    "openstack-infra/system-config" : "tesora/tesora-config",
    "openstack-infra/config" : "tesora/tesora-config",
    "openstack/api-site" : "tesora/tesora-api-site",
    "openstack/horizon" : "tesora/tesora-horizon",
    "openstack/openstack-manuals" : "tesora/tesora-openstack-manuals",
    "openstack/python-troveclient" : "tesora/tesora-python-troveclient",
    "openstack/requirements" : "tesora/tesora-requirements",
    "openstack/trove" : "tesora/tesora-trove",
    "openstack/trove-integration" : "tesora/tesora-trove-integration",
    "openstack/trove-specs" : "tesora/tesora-trove-specs",
}

# Not using an arg libraries in order to avoid module imports that
# are not available across all python versions
if len(sys.argv) > 1:
    GIT_BASE = sys.argv[1]
else:
    GIT_BASE = 'git://git.openstack.org'


# This will allow a subset of repositories to come from elsewhere
# This is used because Tesora only forks a very small subset of repos
# used in devstack.
# This also handles the downstream renaming of repositories by using
# a symlink
def clone_repo_with_override(project):
    dest = override_mappings.get(project)
    if dest is None:
        return clone_repo(project)

    (status, out) = clone_repo(dest, "https://github.com")

    os.symlink('/opt/git/%s' % dest, '/opt/git/%s' % project)
    return (status, out)


# BH: allow GIT_BASE override on a per-call basis
def clone_repo(project, base=GIT_BASE):
    remote = '%s/%s.git' % (base, project)

    # Clear out any existing target directory first, in case of a retry.
    try:
        shutil.rmtree(os.path.join('/opt/git', project))
    except OSError:
        pass

    # Try to clone the requested git repository.
    (status, out) = run_local(['git', 'clone', remote, project],
                              status=True, cwd='/opt/git')

    # If it claims to have worked, make sure we can list branches.
    if status == 0:
        (status, moreout) = run_local(['git', 'branch', '-a'], status=True,
                                      cwd=os.path.join('/opt/git', project))
        out = '\n'.join((out, moreout))

    # If that worked, try resetting to HEAD to make sure it's there.
    if status == 0:
        (status, moreout) = run_local(['git', 'reset', '--hard', 'HEAD'],
                                      status=True,
                                      cwd=os.path.join('/opt/git', project))
        out = '\n'.join((out, moreout))

    # Status of 0 imples all the above worked, 1 means something failed.
    return (status, out)


def main():
    # TODO(jeblair): use gerrit rest api when available
    data = urllib2.urlopen(URL).read()
    for line in data.split('\n'):
        # We're regex-parsing YAML so that we don't have to depend on the
        # YAML module which is not in the stdlib.
        m = PROJECT_RE.match(line)
        if m:
            project = m.group(1)
            dirname = os.path.dirname(project)
            # Skip repos that are inactive
            if not ('attic' in dirname or dirname == 'stackforge'):
                (status, out) = clone_repo_with_override(project)
                print out
                if status != 0:
                    print 'Retrying to clone %s' % m.group(1)
                    (status, out) = clone_repo_with_override(m.group(1))
                    print out
                    if status != 0:
                        raise Exception('Failed to clone %s' % m.group(1))


if __name__ == '__main__':
    main()
