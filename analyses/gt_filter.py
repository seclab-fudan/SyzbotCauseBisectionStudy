import pymysql as mysql
import git
import re
import os

from config import DATA_DIR, DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

LINUX_REPO = git.Repo(os.path.join(DATA_DIR, 'linux'))
LINUX_NEXT_REPO = git.Repo(os.path.join(DATA_DIR, 'linux-next-history'))


def get_commit_list_before_include(commit, to_cmp=None):
    try:
        repo = LINUX_REPO
        if to_cmp is not None:
            repo.commit(to_cmp)
        return repo.git.rev_list(commit).split()
    except:
        repo = LINUX_NEXT_REPO
        if to_cmp is not None:
            repo.commit(to_cmp)
        return repo.git.rev_list(commit).split()


def get_original_crash_commit(file_name):
    cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % file_name)
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        if "bisecting cause commit" not in first_line:
            first_line = f.readline().strip()

    assert "bisecting cause commit" in first_line
    cause_commit = first_line.split()[-1]
    return cause_commit


def get_bad_commit_crash_title_in_stageC(file_name, bisected_commit):
    cause_bisect_path = os.path.join(DATA_DIR, "bisection_log/%s.txt" % file_name)
    start_str = "testing commit %s" % bisected_commit
    end_str = "# git bisect bad %s" % bisected_commit
    flag = False
    crash_title_set = set()
    with open(cause_bisect_path, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            if flag:
                if "run" in line and "crashed:" in line:
                    crash_title = line.split("crashed:")[-1].strip()
                    crash_title_set.add(crash_title)
                elif end_str in line:
                    break
            else:
                if start_str in line:
                    flag = True

    assert len(crash_title_set) > 0
    return crash_title_set


if __name__ == "__main__":
    conn = mysql.connect(host=DB_IP, port=DB_PORT, user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    # from scratch
    # sql = "SELECT bug_id, cause_bisect_log, patch_info, gt_by_time, title, bad_commit FROM syzbot_bug_info WHERE gt_by_time is not NULL and fixes_field_filter is NULL"
    # reproduce from existing database
    sql = "SELECT bug_id, cause_bisect_log, patch_info, gt_by_time, title, bad_commit FROM syzbot_bug_info WHERE gt_by_time is not NULL"
    cursor.execute(sql)
    data = cursor.fetchall()
    print(len(data), "bugs with fixes-field (candidate gt) to process.")

    bug_list = []
    filter_sql = "UPDATE syzbot_bug_info SET fixes_field_filter = %s WHERE bug_id = %s"
    for bug_id, cause_bisect_log, patch_info, gt_by_time, title, bad_commit in data:
        print(bug_id, '...')
        gt_commit = gt_by_time.split(",")[-1]
        original_crash_commit = get_original_crash_commit(cause_bisect_log)

        # F1: gt_commit should be contained by original_crash_commit
        if gt_commit not in get_commit_list_before_include(original_crash_commit, gt_commit):
            print("F1:", bug_id)
            # cursor.execute(filter_sql, (1, bug_id))
            # conn.commit()
            continue

        # F2: patch cannot be contained by original_crash_commit
        # if crash commit contains patch, the patch is wrong (does not fix the bug), thus making fix-field unreliable
        f2 = False
        for patch in patch_info.split(","):
            if patch in get_commit_list_before_include(original_crash_commit, patch):
                print("F2:", bug_id)
                # cursor.execute(filter_sql, (2, bug_id))
                # conn.commit()
                f2 = True
                break
        if f2:
            continue

        # F3: if there exists bad_commit (bisected bad commit) before gt_commit, and the bad_commit contains target bug => gt may be wrong
        if bad_commit is not None:
            assert len(bad_commit) == 40
            if gt_commit not in get_commit_list_before_include(bad_commit, gt_commit):
                re_match_result = re.match(r"([^(]+)(\(\d+\))?", title)
                title = re_match_result.group(1).strip()
                if title in get_bad_commit_crash_title_in_stageC(cause_bisect_log, bad_commit):
                    print("F3:", bug_id)
                    # cursor.execute(filter_sql, (3, bug_id))
                    # conn.commit()
                    continue

        bug_list.append(bug_id)
        # cursor.execute(filter_sql, (0, bug_id))
        # conn.commit()

    print(len(bug_list), "bugs left, others will be filtered.")
    cursor.close()
    conn.close()
