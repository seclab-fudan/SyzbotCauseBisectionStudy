import pymysql as mysql
import os
import git
import seaborn
import matplotlib
import matplotlib.pyplot as plt

from config import DATA_DIR, DB_IP, DB_PORT, DB_USER, DB_PWD, DB_NAME

matplotlib.use('Agg')
plt.rcParams["font.family"] = "Times New Roman"

LINUX_PATH = os.path.join(DATA_DIR, "linux")
LINUX_NEXT_PATH = os.path.join(DATA_DIR, "linux-next-history")

LINUX_REPO = git.Repo(LINUX_PATH)
LINUX_NEXT_REPO = git.Repo(LINUX_NEXT_PATH)


def get_version(commit_id):
    repo = LINUX_REPO
    try:
        repo.commit(commit_id)
    except:
        repo = LINUX_NEXT_REPO

    result = repo.git.show(commit_id + ':Makefile')
    version = None
    patchlevel = None
    for line in result.split('\n'):
        if line.startswith('VERSION ='):
            version = line.split('=')[-1].strip()
        elif line.startswith('PATCHLEVEL ='):
            patchlevel = line.split('=')[-1].strip()
            break
    assert version is not None and patchlevel is not None
    return "v%s.%s" % (version, patchlevel)


def get_version_info(bug_id):
    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT crash_commit_version, ground_truth FROM syzbot_bug_info WHERE bug_id = %s"
    cursor.execute(sql, bug_id)
    data = cursor.fetchone()

    cursor.close()
    conn.close()
    # return data[0], get_version(data[1])
    return parse_version(data[0]), parse_version(get_version(data[1]))


def parse_version(version):
    # return version[1:]
    a, b = version[1:].split('.')
    a = int(a)
    b = int(b) 
    if a >= 5 or (a == 4 and b >= 16):
        return version[1:]
    elif a == 2:
        assert b == 6
        return "2.6"
    elif a == 3:
        assert 0 <= b <= 19
        return "3.0~3.19"
    else:
        assert a == 4 and 0 <= b <= 15
        return "4.0~4.15"


if __name__ == "__main__":
    conn = mysql.connect(host=DB_IP, port=DB_PORT,
                         user=DB_USER, passwd=DB_PWD, db=DB_NAME)
    cursor = conn.cursor()

    sql = "SELECT bug_id FROM syzbot_bug_info WHERE ground_truth is not NULL"
    cursor.execute(sql)
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    crash_version_dict = dict()
    gt_version_dict = dict()
    for (bug_id,) in data:
        crash_version, gt_version = get_version_info(bug_id)
        if crash_version not in crash_version_dict:
            crash_version_dict[crash_version] = 1
        else:
            crash_version_dict[crash_version] += 1

        if gt_version not in gt_version_dict:
            gt_version_dict[gt_version] = 1
        else:
            gt_version_dict[gt_version] += 1

    all_data = []
    for k, v in crash_version_dict.items():
        all_data.append((k, "Crash Commit", v))
    for k, v in gt_version_dict.items():
        all_data.append((k, "Ground-truth Commit", v))

    version_data = {"Version": [], "Category": [], "Number": []}
    for k, c, v in sorted(all_data, key=lambda x: (int(x[0].split(".")[0]), int(x[0].split(".")[1].split("~")[0]), x[1])):
        version_data["Version"].append(k)
        version_data["Category"].append(c)
        version_data["Number"].append(v)

    plt.figure(figsize=(6, 4))
    p = seaborn.barplot(x='Version', y='Number', hue='Category', data=version_data,
                        palette='Blues', edgecolor='w')
    p.set_xlabel("Version", fontsize=13)
    p.set_ylabel("Number", fontsize=13)
    plt.xticks(fontsize=13, rotation=70)
    plt.legend(loc='upper right', fontsize=12)
    plt.tight_layout(pad=0.1)
    plt.savefig('./dataset_distribution.pdf')
