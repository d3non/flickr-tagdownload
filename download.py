import os.path
import requests
import logging
import flickrapi
import KEYS

logging.basicConfig(level=logging.INFO)

LICENSES_OK = set(map(str, range(1, 8)))  # see https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html
TAGS = ['cat', 'funny']

OWNERS = {}


def get_owner_name(user_id):
    if user_id not in OWNERS:
        r = flickr.people.getInfo(user_id=user_id)
        OWNERS[user_id] = r.find('person')
    return OWNERS[user_id]


def safe_url_as(url, path):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
    else:
        raise Exception("error downloading {}, status_code was {}".format(url, r.status_code))

if __name__ == '__main__':

    flickr = flickrapi.FlickrAPI(api_key=KEYS.API_KEY, secret=KEYS.API_SECRET)

    pages = range(1,20)

    for page in pages:
        photos = flickr.photos.search(tags=','.join(TAGS), tag_mode='all', license=','.join(LICENSES_OK),
                                      extras='license,owner_name,url_z,url_o', page=page)

        for p in photos[0]:
            url = p.get('url_z')
            if url is None:
                continue
            path = "{}.jpg".format(p.get('id'))
            if os.path.isfile(path):
                logging.warning("already downloaded image:{}".format(p.get('id')))
                continue
            try:
                logging.info("downloading {}".format(url))
                safe_url_as(url, path)
                license_ = int(p.get('license'))
                if license_ in set(range(1, 7)):
                    logging.info("writing ownership file, since license={}".format(license_))
                    owner = get_owner_name(p.get('owner'))
                    path_credit = "{}.credit".format(p.get('id'))
                    with open(path_credit, 'w') as f:
                        owner_name = owner.find('realname').text
                        f.write("{name} ({url})".format(name=owner_name, url=owner.find('profileurl').text))
            except Exception as e:
                logging.warning(e)