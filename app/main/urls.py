from flask import Blueprint, g

from . import views, collections, explore
from utils import errors
from gitmark.config import GitmarkSettings
from utils import template_filters

main = Blueprint('main', __name__)

main.errorhandler(404)(errors.page_not_found)
main.errorhandler(401)(errors.handle_unauthorized)
main.add_url_rule('/', view_func=views.IndexView.as_view('index'))
main.add_url_rule('/enterprise/', view_func=views.EnterpriseView.as_view('enterprise'))
main.add_url_rule('/users/<username>/', view_func=views.UserView.as_view('user_view'))

main.add_url_rule('/import-repo/', view_func=views.ImportRepoView.as_view('import_repo'), defaults={'starred':True})
main.add_url_rule('/starred-repos/', view_func=views.StarredRepoView.as_view('starred_repos'))
main.add_url_rule('/users/<username>/starred-repos/', view_func=views.StarredRepoView.as_view('user_starred_repos'))
main.add_url_rule('/all-repos/', view_func=views.ReposView.as_view('all_repos'))
main.add_url_rule('/search/github/', view_func=views.GitHubResultView.as_view('github_result'))

main.add_url_rule('/user/collections/', view_func=collections.MyCollectionsView.as_view('my_collections'))
main.add_url_rule('/user/collections/public/', view_func=collections.MyCollectionsView.as_view('my_public_collections'), defaults={'visibility':'public'})
main.add_url_rule('/user/collections/private/', view_func=collections.MyCollectionsView.as_view('my_private_collections'), defaults={'visibility':'private'})
main.add_url_rule('/user/collections/following/', view_func=collections.UserCollectionsView.as_view('following_collections'), defaults={'following':True})
main.add_url_rule('/users/<username>/collections/', view_func=collections.UserCollectionsView.as_view('user_collections'))
main.add_url_rule('/users/<username>/collections/following/', view_func=collections.UserCollectionsView.as_view('user_following_collections'), defaults={'following':True})
main.add_url_rule('/user/collections/<collection_id>/edit/', view_func=collections.MyCollectionEditView.as_view('edit_collection'))
main.add_url_rule('/user/collections/<collection_id>/detail/', view_func=collections.CollectionView.as_view('collection_detail'))
main.add_url_rule('/user/collections/<collection_id>/detail/edit/', view_func=collections.CollectionDetailEditView.as_view('collection_detail_edit'))
main.add_url_rule('/user/collections/<collection_id>/detail/edit/search', view_func=collections.Search4Collection.as_view('collection_detail_edit_search'))

main.add_url_rule('/explore/collections/', view_func=explore.ExploreCollectionView.as_view('explore_collection'))
main.add_url_rule('/explore/repositories/', view_func=views.ReposView.as_view('explore_repository'))


DAOVOICE = GitmarkSettings['daovoice']

@main.before_app_request
def before_request():
    g.allow_daovoice = DAOVOICE['allow_daovoice']
    g.daovoice_app_id = DAOVOICE['app_id']

main.add_app_template_filter(template_filters.urlencode_filter, name='urlencode')
