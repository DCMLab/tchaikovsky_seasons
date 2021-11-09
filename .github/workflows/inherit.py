#!/usr/bin/env python
# coding: utf-8

import argparse, re, time
from itertools import product
import github3 # pip install github3.py

CACHE = {}


def get(what, repo, from_cache=True, **kwargs):
    """ Shorthand for getting stuff from the GitHub API as lists of dicts, caching the results.

    Parameters
    ----------
    what : :obj:`str` or :obj:`tuple`
        | Pass a string to flatten the respective iterator into a list of dicts, e.g. 'issues' -> repo.issues()
        | Pass a tuple to do the same with the iterator on a second level,
        | ('issue', 'labels') for repo.issue(n).labels() assuming you pass number=n as keyword argument.
    repo: :obj:`github3.repos.repo.Repository`
        The GitHub repo to GET from.
    from_cache : :obj:`bool`, optional
        By default, the data is fetched only once. Pass False to fetch anew and update the cache.
    kwargs :
        Keyword arguments are passed to the first method called on the repo.

    """
    key = (repo.name, what) + tuple(kwargs.values())
    if from_cache and key in CACHE:
        return CACHE[key]
    if isinstance(what, tuple):
        frst, scnd, *_ = what
        item = repo.__getattribute__(frst)(**kwargs)
        it = item.__getattribute__(scnd)
        if callable(it):
            it = it()
    else:
        it = repo.__getattribute__(what)(**kwargs)

    try:
        res = [i.as_dict() for i in it]
    except:
        try:
            res = [it.as_dict()]
        except:
            res = it
    CACHE[key] = res
    return res



def copy_between_issues(repo, from_number, to_number, assignees=True, labels=True):
    """"""
    add_to_this = repo.issue(to_number)

    def add_missing(what, items):
        """"""
        if what == 'assignees':
            if add_to_this.add_assignees(items):
                new_items = [user_cache[user] for user in items]
                # unfortunately, add_assignees() does not return the correspoding user objects,
                # which is why they were cached
        elif what == 'labels':
            new_items = add_to_this.add_labels(*items)
            # add_to_this does return the new label objects
        key = (repo.name, ('issue', what), to_number)
        CACHE[key].extend(new_items)

    l = locals()
    what = [param for param in ('assignees', 'labels') if l[param]]
    combinations = product((from_number, to_number), what)
    current_data = {(issue_number, param): get(('issue', param), repo, number=issue_number) for issue_number, param in combinations}
    user_cache = {user['login']: user for (issue_number, param), user_list in current_data.items() for user in user_list if param == 'assignees'}
    comparison_keys = {'assignees': 'login', 'labels': 'name'}
    for param in what:
        fro, to = current_data[(from_number, param)], current_data[(to_number, param)]
        key = comparison_keys[param]
        fro_items, to_items = [f[key] for f in fro], [t[key] for t in to]
        missing = [item for item in fro_items if item not in to_items]
        if len(missing) > 0:
            add_missing(param, missing)
            print(f"The following {param} have been copied from #{from_number} to #{to_number}: {', '.join(missing)}")
            time.sleep(0.25)
        elif len(fro_items) > 0:
            print(f"#{to_number} already had all the {param} of #{from_number}.")
        else:
            print(f"No {param} to copy from #{from_number}")


def find_pr_by_sha(repo, sha, state='open'):
    prs = get('pull_requests', repo, state=state)
    try:
        return next(pr for pr in prs if pr['head']['sha'] == sha)
    except:
        return None


def find_referenced_issues(html):
    find_issues = r"/issues/(\d+)"
    if isinstance(html, str):
        return set(re.findall(find_issues, html))
    else:
        return set()

def get_referenced_issues(repo, issue_number=None):
    issue = repo.issue(issue_number)
    referenced_issues = set()
    referenced_issues.update(find_referenced_issues(issue.body_html))
    for comment in issue.comments():
        referenced_issues.update(find_referenced_issues(comment.body_html))
    if len(referenced_issues) > 0:
        print(f"Issue #{issue_number} refers to {', '.join(f'#{i}' for i in referenced_issues)}")
    else:
        print("Nothing to do.")
    return referenced_issues


def split_repo_name(s):
    try:
        owner, repo_name, *_  = s.split('/')
    except:
        print(f"Repository identifier {s} could not be split into its owner/repo_name components.")
        raise
    return owner, repo_name

def main(args):
    owner, repo_name = split_repo_name(args.repository)
    gh = github3.login(token=args.token)
    repo = gh.repository(owner, repo_name)
    if len(args.pull_request) == 0:
        assert args.sha is not None, "Either --pull_request or --sha need to be specified."
        pr = find_pr_by_sha(repo, args.sha)
        if pr is None:
            raise ValueError(f"None of the open pull requests has the following commit as HEAD: {sha}")
        prs = [pr.number]
    else:
        prs = [int(pr.strip('#')) for pr in args.pull_request]
    for pr_number in prs:
        from_numbers = get_referenced_issues(repo, pr_number)
        for fro in from_numbers:
            copy_between_issues(repo, fro, pr_number)


################################################################################
#                           COMMANDLINE INTERFACE
################################################################################
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description = '''\
----------------------------------------------------------------------------------------
| Script for a Pull request to inherit labels and assignees from the associated issues |
----------------------------------------------------------------------------------------

Description goes here

''')
    parser.add_argument('repository', help='GitHub repository in the format owner/repo_name')
    parser.add_argument('token', help='Personal access token granted access rights to the repository in question.')
    parser.add_argument('-p', '--pull_request', nargs='*', help='Number(s) of the pull request(s) that is/are to inherit labels and assignees.')
    parser.add_argument('-s', '--sha', help="If the number of the pull request is unkown, you can pass the SHA of its HEAD, i.e., of its latest commit.")
    args = parser.parse_args()
    main(args)
