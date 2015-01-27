import os
import sys
import traceback
import requests
import logging
import flickrapi
import argparse

import KEYS

logging.basicConfig(level=logging.INFO)

LICENSES_OK = set(map(str, range(1, 8)))  # see https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html
LICENSE_TEXT_DEFAULT = """Image by '{owner[realname][_content]}' ({owner[profileurl][_content]})
Shared under the {license[name]} ({license[url]})
"""
LICENSE_TEXT_DEFAULT_CSV = """{owner[realname][_content]},{owner[profileurl][_content]},{license[name]},{license[url]}"""
LICENSE_ACTIONS = {
    '1': LICENSE_TEXT_DEFAULT,
    '2': LICENSE_TEXT_DEFAULT,
    '3': LICENSE_TEXT_DEFAULT,
    '4': LICENSE_TEXT_DEFAULT,
    '5': LICENSE_TEXT_DEFAULT,
    '6': LICENSE_TEXT_DEFAULT,
}

OWNERS = {}


def get_owner(user_id):
    if user_id not in OWNERS:
        user = flickr.people.getInfo(user_id=user_id)['person']
        if 'realname' not in user:
            user['realname'] = {'_content': ""}
        OWNERS[user_id] = user
    return OWNERS[user_id]


def save_url_as(url, path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
    else:
        raise Exception("error downloading {}, status_code was {}".format(url, r.status_code))


def license_default_action(text, **context):
    path_credit = os.path.join(context['BASE_PATH'], "{photo[id]}.license".format_map(context))
    logging.info("writing license file: %s" % path_credit)
    with open(path_credit, 'w') as f:
        f.write(text.format_map(context))

arg_parser = argparse.ArgumentParser(description='download images by tag from flickr (including their license information)')
arg_parser.add_argument('--directory', help="save images in DIRECTORY")
arg_parser.add_argument('--csv', default=False, help="save license information in CSV format")
arg_parser.add_argument('-p', '--pages', dest='pages', type=int, default=1, help="download all images on pages up to PAGES")
arg_parser.add_argument('--perpage', type=int, default=50, help="search query should have PERPAGES images per page")
arg_parser.add_argument('--skip', type=int, default=0, help="skip the first SKIP pages")
arg_parser.add_argument('--nolicense', action='store_true', default=False, help="do not create license files for images")
arg_parser.add_argument('--exclude', action='append', default=[], help="add these tags with leading - to search")
arg_parser.add_argument('--any', action='store_true', default=False, help="tags are OR combined in stead of AND")
arg_parser.add_argument('tag', nargs='+', help="search images by these tags")

if __name__ == '__main__':

    args = arg_parser.parse_args()
    logging.info(args)

    flickr = flickrapi.FlickrAPI(api_key=KEYS.API_KEY, secret=KEYS.API_SECRET, format='parsed-json')
    licenses = {x['id']: x for x in flickr.photos.licenses.getInfo()['licenses']['license']}
    if args.csv:
        LICENSE_ACTIONS = {str(x): LICENSE_TEXT_DEFAULT_CSV for x in range(1, 7)}

    BASE_PATH = ""
    if 'directory' in args and args.directory:
        if not os.path.exists(args.directory):
            os.makedirs(args.directory)
        BASE_PATH = args.directory

    for page in range(1 + args.skip, args.pages + 1):
        search = flickr.photos.search(tags=','.join(args.tag) + ','.join(map(lambda x: '-%s' % x, args.exclude)),
                                      tag_mode='all' if not args.any else 'any',
                                      page=page, per_page=args.perpage,
                                      license=','.join(LICENSES_OK),
                                      extras='license,url_z,url_o', media='photo', content_type=1)

        for photo in search['photos']['photo']:
            try:
                photo['url'] = photo['url_z']
                if photo['url'] is None:
                    continue
                path = os.path.join(BASE_PATH, "{id}.jpg".format(**photo))
                if os.path.isfile(path):
                    logging.warning("already downloaded image:{id}".format_map(photo))
                    continue
                logging.info("downloading {url}".format(**photo))
                save_url_as(photo['url'], path)
                if not args.nolicense and photo['license'] in LICENSE_ACTIONS:
                    action = LICENSE_ACTIONS[photo['license']]
                    context = {'photo': photo, 'license': licenses[photo['license']],
                               'owner': get_owner(photo['owner']), 'BASE_PATH': BASE_PATH}
                    if hasattr(action, '__call__'):
                        action(**context)
                    else:
                        license_default_action(text=action, **context)
            except Exception as e:
                print('-'*60)
                traceback.print_exc(file=sys.stdout)
                print('-'*60)