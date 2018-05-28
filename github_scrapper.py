import requests
import re
import os
import datetime
import sys
import csv

def parse_nested_objects(d):
    """
    this function returns a one level dicitonnary without nested objects
    """
    for key in list(d):
        value = d[key]
        if type(value) is dict:
            parse_nested_objects(value)
            for k, v in value.items():
                d[key + '-' + k] = v
            d.pop(key)

def build_csv(d_list):
    """
    build a csv from a list of dictionnaries
    """
    #get one leveled dicitonnaries
    for d in d_list:
        parse_nested_objects(d)
    csv = {}
    #get the header columns of the csv
    for d in d_list:
        for k in d.keys():
            if not k in csv:
                csv[k] = []
    # get the values of the csv
    for d in d_list:
        for k in csv.keys():
            if k in d:
                csv[k].append(d[k])
            else:
                csv[k].append(None)
    return csv

def esc(val):
    string = str(val).replace("'", ' ')
    if ',' in string or "\n" in string:
        return "'" + string + "'"
    return string

def write_csv(csv, main_org):
    with open(main_org + '_repos.csv', 'w') as f:
        headers = ['id', 'name', 'full_name', 'description', 'fork', 'created_at', 'updated_at', 'homepage', 'size', 'stargazers_count', 'language', 'forks_count', 'archived', 'open_issues_count', 'owner-login', 'license-key', 'license-name']
        headers = [h for h in headers if h in list(csv)]
        for i, head in enumerate(headers):
            f.write(esc(head))
            if i < len(headers) - 1:
                f.write(',')
        f.write("\n")
        length = len(csv[headers[0]])
        for head, values in csv.items():
            if length != len(values):
                raise Exception('Missing values in csv')
        for i in range(length):
            for j, head in enumerate(headers):
                values = csv[head]
                f.write(esc(values[i]))
                if j < len(headers) - 1:
                    f.write(',')
            f.write("\n")

def print_repos_ids(repos_list):
    for rep in repos_list:
        print(rep['id'])

def get_next_page(request):
    try:
        link_header = request.headers['Link']
    except KeyError:
        if request.headers['Status'] == '200 OK':
            return None
        print(request.json())
        raise
    parts = link_header.split(',')
    for p in parts:
        if 'next' in p:
            m = re.search('<(?P<next_link>.*?)>; rel="next"', p)
            if m:
                return m.group('next_link')
    return None

def make_request(url):
    url += '&access_token=' + os.environ['GITHUB_TOKEN']
    print(url)
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception("Error code")
    return r

def get_org_repos(org):
    link = 'https://api.github.com/orgs/'+ org +'/repos?'
    print(link)
    r = make_request(link)
    repos = r.json()
    next_link = get_next_page(r)
    while next_link:
        print(next_link)
        r = requests.get(next_link)
        repos += r.json()
        next_link = get_next_page(r)
    return repos

def make_csv_from_repo_id(ids):
    ids = ids[610:]
    with open('most_starred_repos1.csv', 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file, delimiter=',', quotechar="'")
        writer.writerow(['id','name','stars','owner_name','owner_id','owner_type','owner_blog','owner_location','owner_bio','owner_company'])
        for i, repo_id in enumerate(ids):
            print(i)
            val = []
            link = 'https://api.github.com/repositories/' + str(repo_id) + '?'
            r = make_request(link)
            repo = r.json()
            owner_login = repo['owner']['login']
            val.append(str(repo['id']))
            val.append(repo['name'])
            val.append(str(repo['stargazers_count']))
            val.append(owner_login)
            link = 'https://api.github.com/users/' + owner_login + '?'
            r = make_request(link)
            owner = r.json()
            val.append(str(owner['id']))
            val.append(owner['type'])
            val.append(owner['blog'])
            val.append(owner['location'])
            val.append(owner['bio'])
            val.append(owner['company'])
            writer.writerow(val)

def get_user_company(login):
    link = 'https://api.github.com/users/'+ login +'?'
    r = make_request(link)
    company = r.json()['company']
    return company

def make_best_guess(cmps):
    d = {}
    for cmp in cmps:
        if not cmp or cmp.strip() == '':
            continue
        if cmp in d:
            d[cmp] += 1
        else:
            d[cmp] = 1
    print(d)
    max = 0
    max_k = None
    for cmp in d:
        if d[cmp] > max:
            max_k = cmp
            max = d[cmp]
    if max > 1:
        return max_k
    return None

def guess_company(org):
    members_logins = []
    link = 'https://api.github.com/orgs/' + org + '/public_members?'
    r = make_request(link)
    members = r.json()
    for m in members:
        members_logins.append(m['login'])
    """
    link = get_next_page(r)
    while link:
        r = make_request(link)
        members = r.json()
        for m in members:
            members_ids.append(m['id'])
        link = get_next_page(r)
    """
    members_logins = members_logins[:10]
    members_company = []
    for login in members_logins:
        cmp = get_user_company(login)
        members_company.append(cmp)
    guess = make_best_guess(members_company)
    return guess

def fill_company(csv_name, dest_file):
    with open(dest_file, 'w', newline='', encoding='utf-8') as dst:
        writer = csv.writer(dst, delimiter=',', quotechar="'")
        with open(csv_name, newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=',', quotechar="'")
            for i, row in enumerate(reader):
                print(i)
                if reader.line_num > 1 and len(row) > 9 and row[9] == '' and row[5] == 'Organization':
                    cmp = guess_company(row[3])
                    row[9] = cmp
                    writer.writerow(row)
                else:
                    writer.writerow(row)

def get_most_starred_repos(n):
    ids = []
    link = 'https://api.github.com/search/repositories?q=stars:%3E1&s:stars'
    while len(ids) < n:
        r = make_request(link)
        repos = r.json()['items']
        for repo in repos:
            ids.append(repo['id'])
        link = get_next_page(r)
    return ids[:n]

def main():
    if len(sys.argv) < 2:
        print("This script builds a csv of chosen github organizations repositories\nUsage: python3 github_scrapper.py google facebook tenserflow ...")
    else:
        orgs = sys.argv[1:]
        repos = []
        for org in orgs:
            print("Scrapping the repositories of the '" + org + "' organization")
            try:
                repos += get_org_repos(org)
            except Exception as e:
                print(e)
                print("ERROR: could not scrap the repositiories of the '" + org + "' organization properly")
        csv = build_csv(repos)
        write_csv(csv, orgs[0])
    return

if __name__ == '__main__':
    main()
