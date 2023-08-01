import pymysql as mysql
import git
import re
import os
import json
import dreamutil
from scipy import stats

from config import DATA_DIR, DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

LINUX_PATH = os.path.join(DATA_DIR, "linux")
LINUX_NEXT_PATH = os.path.join(DATA_DIR, "linux-next-history")

LINUX_REPO = git.Repo(LINUX_PATH)
LINUX_NEXT_REPO = git.Repo(LINUX_NEXT_PATH)


def format_int(num):
    return "{:,}".format(num)


def format_float(num):
    return "{:,.2f}".format(num)


def list2str(list):
    str = ""
    for ele in list:
        str += ele + ","
    return str.strip(",")


def str2list(str):
    list = []
    if str != '' and str is not None:
        list = str.split(",")
    return list


def is_commit_exist(commit_list):
    repo = LINUX_REPO
    for c in commit_list:
        try:
            repo.commit(c)
        except:
            return False
    return True


def is_same_file_changed(a, b):
    if is_commit_exist((a, b)):
        repo = LINUX_REPO
    else:
        repo = LINUX_NEXT_REPO

    commit_a = repo.commit(a)
    commit_b = repo.commit(b)
    if len(commit_a.parents) == 0 or len(commit_b.parents) == 0:
        # print("Warning: initial commit.")
        return True, None  # FIXME: is initial commit must contain all the files?

    af1, af2 = dreamutil.get_file_changed(repo, a)
    bf1, bf2 = dreamutil.get_file_changed(repo, b)
    changed_files_a = af1 + [xx for x in af2 for xx in x]
    changed_files_b = bf1 + [xx for x in bf2 for xx in x]

    same_file_set = set(changed_files_a).intersection(set(changed_files_b))
    return len(same_file_set) > 0, same_file_set


def is_same_function_changed(a, b):
    if is_commit_exist((a, b)):
        repo = LINUX_REPO
    else:
        repo = LINUX_NEXT_REPO

    commit_a = repo.commit(a)
    commit_b = repo.commit(b)
    if len(commit_a.parents) == 0 or len(commit_b.parents) == 0:
        # print("Warning: initial commit.")
        return True, None  # FIXME: is initial commit must contain all the functions?

    has_same_file, same_file_set = is_same_file_changed(a, b)
    if has_same_file:
        function_changed_a = dreamutil.get_function_changed(
            repo, a, file_scope=same_file_set)
        function_changed_b = dreamutil.get_function_changed(
            repo, b, file_scope=same_file_set)
        same_func_changed = function_changed_a.intersection(function_changed_b)
        return len(same_func_changed) > 0, same_func_changed
    else:
        return False, set()


def is_meaningful_line(line):
    KEYWORDS = ("auto", "break", "case", "char",
                "const", "continue", "default", "do",
                "double", "else", "enum", "extern",
                "float", "for", "goto", "if", "endif",
                "int", "long", "register", "return",
                "short", "signed", "sizeof", "static",
                "struct", "switch", "typedef", "union",
                "unsigned", "void", "volatile", "while",
                "inline", "restrict", "_Bool", "_Complex", "_Imaginary",
                "_Alignas", "_Alignof", "_Atomic", "_Static_assert", "_Noreturn",
                "_Thread_local", "_Generic", "__attribute__", "define")
    for k in KEYWORDS:
        line = line.replace(k, "")
    for s in line:
        if s.isalpha() or s.isdigit():
            return True
    return False


def is_same_line_related(a, b):
    if is_commit_exist((a, b)):
        repo = LINUX_REPO
    else:
        repo = LINUX_NEXT_REPO

    commit_a = repo.commit(a)
    commit_b = repo.commit(b)
    if len(commit_a.parents) == 0 or len(commit_b.parents) == 0:
        # print("Warning: initial commit.")
        return False, None  # FIXME: initial commit does not contain same lines?

    has_same_file, same_file_set = is_same_file_changed(a, b)
    if has_same_file:
        function_changed_with_line_info_a = dreamutil.get_function_changed(
            repo, a, file_scope=same_file_set, verbose=True)
        function_changed_with_line_info_b = dreamutil.get_function_changed(
            repo, b, file_scope=same_file_set, verbose=True)
        same_line = []
        for file_a, add_info_a in function_changed_with_line_info_a["Add"].items():
            for func_a, add_line_in_func_a in add_info_a.items():
                if file_a in function_changed_with_line_info_b["Delete"] and func_a in function_changed_with_line_info_b["Delete"][file_a]:
                    for _, line_content_a in add_line_in_func_a:
                        for _, line_content_b in function_changed_with_line_info_b["Delete"][file_a][func_a]:
                            if line_content_a == line_content_b and is_meaningful_line(line_content_a):
                                same_line.append(line_content_a)

        for file_a, delete_info_a in function_changed_with_line_info_a["Delete"].items():
            for func_a, delete_line_in_func_a in delete_info_a.items():
                if file_a in function_changed_with_line_info_b["Add"] and func_a in function_changed_with_line_info_b["Add"][file_a]:
                    for _, line_content_a in delete_line_in_func_a:
                        for _, line_content_b in function_changed_with_line_info_b["Add"][file_a][func_a]:
                            if line_content_a == line_content_b and is_meaningful_line(line_content_a):
                                same_line.append(line_content_a)
        return len(same_line) > 0, same_line
    else:
        return False, []


def get_commit_maintainers(commit_list):
    if is_commit_exist(commit_list):
        repo = LINUX_REPO
    else:
        repo = LINUX_NEXT_REPO

    maintainers = []
    patterns = [re.compile(r"^Reviewed\-.*: (.*)$"),
                re.compile(r"^[A-Za-z-]+\-and\-[Rr]eviewed\-.*: (.*)$"),
                re.compile(r"^Acked\-.*: (.*)$"),
                re.compile(r"^[A-Za-z-]+\-and\-[Aa]cked\-.*: (.*)$"),
                re.compile(r"^Tested\-.*: (.*)$"),
                re.compile(r"^[A-Za-z-]+\-and\-[Tt]ested\-.*: (.*)$"),
                re.compile(r"^Signed-off-by: (.*)$")]
    for commit in commit_list:
        # 1. commit author
        author = repo.commit(commit).author
        maintainers.append([author.name, author.email])
        # 2. developers mentioned in commit message, e.g., Reviewed by, Acked by
        for line in repo.commit(commit).message.split('\n'):
            if "<" in line and ">" in line:
                for p in patterns:
                    r = p.search(line)
                    if r is not None:
                        rr = re.search(r"\"?([^\"]+)\"? <(.+)>", r.group(1))
                        if rr is not None:
                            maintainers.append([rr.group(1), rr.group(2)])
    return maintainers


def get_patch_authors(patch_list):
    if is_commit_exist(patch_list):
        repo = LINUX_REPO
    else:
        repo = LINUX_NEXT_REPO

    authors = []
    for p in patch_list:
        authors.append([repo.commit(p).author.name, repo.commit(p).author.email])
    return authors


def is_author_included(maintainers, authors, NAME=True, EMAIL=True):
    maintainers_cmp = set()
    authors_cmp = set()
    if NAME and EMAIL:
        for m in maintainers:
            maintainers_cmp.add(m[0]+m[1])
        for a in authors:
            authors_cmp.add(a[0]+a[1])
    elif NAME and not EMAIL:
        for m in maintainers:
            maintainers_cmp.add(m[0])
        for a in authors:
            authors_cmp.add(a[0])
    elif not NAME and EMAIL:
        for m in maintainers:
            maintainers_cmp.add(m[1])
        for a in authors:
            authors_cmp.add(a[1])
    
    return len(maintainers_cmp.intersection(authors_cmp)) > 0


def is_same_file_changed_between_commit_lists(commit_list_a, commit_list_b):
    for a in commit_list_a:
        for b in commit_list_b:
            if is_same_file_changed(a, b)[0]:
                return True
    return False


def is_same_function_changed_between_commit_lists(commit_list_a, commit_list_b):
    for a in commit_list_a:
        for b in commit_list_b:
            if is_same_function_changed(a, b)[0]:
                return True
    return False


def is_same_line_related_between_commit_lists(commit_list_a, commit_list_b):
    for a in commit_list_a:
        for b in commit_list_b:
            line_related, line_related_info = is_same_line_related(a, b)
            if line_related:
                # print(a, b, line_related_info)
                return True
    return False


def is_patch_author_included_by_bisection(result_commit_list, patch_commit_list, NAME=True, EMAIL=True):
    return is_author_included(get_commit_maintainers(result_commit_list), get_patch_authors(patch_commit_list), NAME=NAME, EMAIL=EMAIL)


def is_patch_author_included_by_crash_report(bug_id, patch_commit_list, NAME=True, EMAIL=True):
    with open("maintainers_crash_report.json", mode="r", encoding="utf-8") as f:
        maintainers = json.load(f)[bug_id]
        return is_author_included(maintainers, get_patch_authors(patch_commit_list), NAME=NAME, EMAIL=EMAIL)


if __name__ == "__main__":
    # dataset: patch time >= report time
    # granuality: Bug
    correct_bisect_dict = {"count": 0, "code_no_relation": 0, "same_file": 0, "same_function": 0, "same_line": 0,
                           "same_author": 0, "same_author_crash_report": 0}
    incorrect_bisect_dict = {"count": 0, "code_no_relation": 0, "same_file": 0, "same_function": 0, "same_line": 0,
                             "same_author": 0, "same_author_crash_report": 0}

    NAME_CMP = True
    EMAIL_CMP = True

    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT bug_id, bad_commit, inconclusive_commit, ground_truth, patch_info FROM syzbot_bug_info WHERE ground_truth is NOT NULL and DATEDIFF(patch_time, report_time) >= 0"
    cursor.execute(sql)
    data = cursor.fetchall()

    for bug_id, bad_commit, inconclusive_commit, ground_truth, patch_info in data:
        if bad_commit is None and inconclusive_commit is None:  # no output
            pass
        else:
            cause_bisection_result_list = [bad_commit]
            if inconclusive_commit is not None:
                cause_bisection_result_list.extend(inconclusive_commit.split(","))

            patch_list = str2list(patch_info)
            if ground_truth in cause_bisection_result_list:
                correct_bisect_dict["count"] += 1
                if is_same_file_changed_between_commit_lists(cause_bisection_result_list, patch_list):
                    correct_bisect_dict["same_file"] += 1
                    if is_same_function_changed_between_commit_lists(cause_bisection_result_list, patch_list):
                        correct_bisect_dict["same_function"] += 1
                        if is_same_line_related_between_commit_lists(cause_bisection_result_list, patch_list):
                            correct_bisect_dict["same_line"] += 1
                else:
                    correct_bisect_dict["code_no_relation"] += 1

                if is_patch_author_included_by_bisection(cause_bisection_result_list, patch_list, NAME=NAME_CMP, EMAIL=EMAIL_CMP):
                    correct_bisect_dict["same_author"] += 1

                if is_patch_author_included_by_crash_report(bug_id, patch_list, NAME=NAME_CMP, EMAIL=EMAIL_CMP):
                    correct_bisect_dict["same_author_crash_report"] += 1
            else:
                incorrect_bisect_dict["count"] += 1
                if is_same_file_changed_between_commit_lists(cause_bisection_result_list, patch_list):
                    incorrect_bisect_dict["same_file"] += 1
                    if is_same_function_changed_between_commit_lists(cause_bisection_result_list, patch_list):
                        incorrect_bisect_dict["same_function"] += 1
                        if is_same_line_related_between_commit_lists(cause_bisection_result_list, patch_list):
                            incorrect_bisect_dict["same_line"] += 1
                else:
                    incorrect_bisect_dict["code_no_relation"] += 1

                if is_patch_author_included_by_bisection(cause_bisection_result_list, patch_list, NAME=NAME_CMP, EMAIL=EMAIL_CMP):
                    incorrect_bisect_dict["same_author"] += 1

                if is_patch_author_included_by_crash_report(bug_id, patch_list, NAME=NAME_CMP, EMAIL=EMAIL_CMP):
                    incorrect_bisect_dict["same_author_crash_report"] += 1

    cursor.close()
    conn.close()

    print("Correct count: %s, same_author: %s (%s%%), same_author_crash_report: %s (%s%%), same_line: %s (%s%%), same_function: %s (%s%%), same_file: %s (%s%%), others: %s (%s%%)" % 
            (format_int(correct_bisect_dict["count"]), 
             format_int(correct_bisect_dict["same_author"]),
             format_float(correct_bisect_dict["same_author"] / correct_bisect_dict["count"] * 100),
             format_int(correct_bisect_dict["same_author_crash_report"]),
             format_float(correct_bisect_dict["same_author_crash_report"] / correct_bisect_dict["count"] * 100),
             format_int(correct_bisect_dict["same_line"]),
             format_float(correct_bisect_dict["same_line"] / correct_bisect_dict["count"] * 100),
             format_int(correct_bisect_dict["same_function"]),
             format_float(correct_bisect_dict["same_function"] / correct_bisect_dict["count"] * 100),
             format_int(correct_bisect_dict["same_file"]),
             format_float(correct_bisect_dict["same_file"] / correct_bisect_dict["count"] * 100),
             format_int(correct_bisect_dict["code_no_relation"]),
             format_float(correct_bisect_dict["code_no_relation"] / correct_bisect_dict["count"] * 100),
             ))

    print("Incorrect count: %s, same_author: %s (%s%%), same_author_crash_report: %s (%s%%), same_line: %s (%s%%), same_function: %s (%s%%), same_file: %s (%s%%), others: %s (%s%%)" % 
            (format_int(incorrect_bisect_dict["count"]), 
             format_int(incorrect_bisect_dict["same_author"]),
             format_float(incorrect_bisect_dict["same_author"] / incorrect_bisect_dict["count"] * 100),
             format_int(incorrect_bisect_dict["same_author_crash_report"]),
             format_float(incorrect_bisect_dict["same_author_crash_report"] / incorrect_bisect_dict["count"] * 100),
             format_int(incorrect_bisect_dict["same_line"]),
             format_float(incorrect_bisect_dict["same_line"] / incorrect_bisect_dict["count"] * 100),
             format_int(incorrect_bisect_dict["same_function"]),
             format_float(incorrect_bisect_dict["same_function"] / incorrect_bisect_dict["count"] * 100),
             format_int(incorrect_bisect_dict["same_file"]),
             format_float(incorrect_bisect_dict["same_file"] / incorrect_bisect_dict["count"] * 100),
             format_int(incorrect_bisect_dict["code_no_relation"]),
             format_float(incorrect_bisect_dict["code_no_relation"] / incorrect_bisect_dict["count"] * 100),
             ))

    #### p-value of Wilcoxon rank-sum test ####
    for type in ("same_author", "same_line", "same_function", "same_file"):
        correct_list = [1] * correct_bisect_dict[type] + [0] * (correct_bisect_dict["count"] - correct_bisect_dict[type])
        incorrect_list = [1] * incorrect_bisect_dict[type] + [0] * (incorrect_bisect_dict["count"] - incorrect_bisect_dict[type])
        _, p_value = stats.ranksums(correct_list, incorrect_list)
        print("%s p-value: %s" % (type, p_value))

        if type == "same_author":
            crash_report_list = [1] * correct_bisect_dict["same_author_crash_report"] + [0] * (correct_bisect_dict["count"] - correct_bisect_dict["same_author_crash_report"])
            _, p_value = stats.ranksums(correct_list, crash_report_list)
            print("author-correct_bisection-vs-crash_report p-value: %s" % p_value)
    

    '''
    statistics-v0
    Correct count: 308, same_author: 190 (61.69%), same_author_or_committer: 285 (92.53%), same_line: 176 (57.14%), same_function: 250 (81.17%), same_file: 280 (90.91%), others: 28 (9.09%)
    Incorrect count: 395, same_author: 93 (23.54%), same_author_or_committer: 173 (43.80%), same_line: 8 (2.03%), same_function: 24 (6.08%), same_file: 67 (16.96%), others: 328 (83.04%)

    statistics-v1:
    NAME and EMAIL
    Correct count: 308, same_author: 217 (70.45%), same_author_crash_report: 123 (39.94%), same_line: 176 (57.14%), same_function: 250 (81.17%), same_file: 280 (90.91%), others: 28 (9.09%)
    Incorrect count: 395, same_author: 100 (25.32%), same_author_crash_report: 133 (33.67%), same_line: 8 (2.03%), same_function: 24 (6.08%), same_file: 67 (16.96%), others: 328 (83.04%)
    same_author p-value: 8.892132066773386e-25
    author-correct_bisection-vs-crash_report p-value: 5.579288133024473e-11
    same_line p-value: 3.9833639097678254e-36
    same_function p-value: 1.5341269157941177e-65
    same_file p-value: 1.3031741963465427e-63

    NAME
    Correct count: 308, same_author: 226 (73.38%), same_author_crash_report: 149 (48.38%), same_line: 176 (57.14%), same_function: 250 (81.17%), same_file: 280 (90.91%), others: 28 (9.09%)
    Incorrect count: 395, same_author: 103 (26.08%), same_author_crash_report: 158 (40.00%), same_line: 8 (2.03%), same_function: 24 (6.08%), same_file: 67 (16.96%), others: 328 (83.04%)
    same_author p-value: 4.770230634086639e-27
    same_line p-value: 3.9833639097678254e-36
    same_function p-value: 1.5341269157941177e-65
    same_file p-value: 1.3031741963465427e-63

    EMAIL
    Correct count: 308, same_author: 217 (70.45%), same_author_crash_report: 126 (40.91%), same_line: 176 (57.14%), same_function: 250 (81.17%), same_file: 280 (90.91%), others: 28 (9.09%)
    Incorrect count: 395, same_author: 100 (25.32%), same_author_crash_report: 139 (35.19%), same_line: 8 (2.03%), same_function: 24 (6.08%), same_file: 67 (16.96%), others: 328 (83.04%)
    same_author p-value: 8.892132066773386e-25
    same_line p-value: 3.9833639097678254e-36
    same_function p-value: 1.5341269157941177e-65
    same_file p-value: 1.3031741963465427e-63
    '''
