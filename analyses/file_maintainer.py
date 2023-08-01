import pymysql as mysql
import git
import os
import re
import json

from config import DATA_DIR, DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

LINUX_NEXT_PATH = os.path.join(DATA_DIR, "linux-next-history")
LINUX_NEXT_REPO = git.Repo(LINUX_NEXT_PATH)


def get_original_crash_commit(file_name):
    cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % file_name)
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if "bisecting cause commit" not in first_line:
            first_line = f.readline().strip()

    assert "bisecting cause commit" in first_line
    cause_commit = first_line.split()[-1]
    return cause_commit


def checkout_commit(commit, repo):
    repo.commit(commit)
    repo.git.reset('--hard')
    repo.git.clean('-fdx')
    repo.git.checkout(commit)


def get_maintainers_impl(file, blame=False):
    args = ["--git-min-percent=15"]
    if blame:
        args.append("--git-blame")
    args.append("-f")
    args.append(file)

    saved_dir = os.getcwd()
    os.chdir(LINUX_NEXT_PATH)
    maintainer_output = os.popen("scripts/get_maintainer.pl %s" % (" ".join(str(a) for a in args)))
    maintainer_output = maintainer_output.read()
    os.chdir(saved_dir)

    result = []
    pattern = re.compile(r"\"?([^\"]+)\"? <(.+)>")
    for line in maintainer_output.strip().split("\n"):
        if "<" in line:
            assert ">" in line
            r = pattern.search(line)
            name, mail = r.group(1), r.group(2)
            result.append((name, mail))
    return result


def get_maintainers(file, crash_commit):
    try:
        LINUX_NEXT_REPO.git.show("%s:%s" % ("master", file))
        maintainer_list = get_maintainers_impl(file)
        if len(maintainer_list) <= 1:
            maintainer_list = get_maintainers_impl(file, blame=True)
        return maintainer_list
    except:
        try:
            LINUX_NEXT_REPO.git.show("%s:%s" % (crash_commit, file))
            checkout_commit(crash_commit, LINUX_NEXT_REPO)
            maintainer_list = get_maintainers_impl(file)
            if len(maintainer_list) <= 1:
                maintainer_list = get_maintainers_impl(file, blame=True)
            checkout_commit("master", LINUX_NEXT_REPO)
            return maintainer_list
        except:
            return []


if __name__ == "__main__":
    conn = mysql.connect(host=DB_IP, port=DB_PORT, user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()
    sql = "SELECT bug_id, cause_bisect_log FROM syzbot_bug_info WHERE ground_truth is NOT NULL and DATEDIFF(patch_time, report_time) >= 0"
    cursor.execute(sql)
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    json_content = dict()
    for bug_id, cause_bisect_log in data:
        crash_commit = get_original_crash_commit(cause_bisect_log)
        with open(os.path.join(DATA_DIR, "sample_crash_report/%s" % bug_id), mode="r") as f:
            guilty_file = f.readline()
            maintainer_list = get_maintainers(guilty_file, crash_commit)
            json_content[bug_id] = maintainer_list

    with open("maintainers_crash_report.json", "w", encoding="utf-8") as f:
        json.dump(json_content, f, indent=4)
