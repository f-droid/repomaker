var rmRepoAppsHeaderSearch = document.getElementById('id_search')
var rmRepoAppsHeaderSearchInput = document.getElementById('rm-repo-apps-header-search-input')
if (rmRepoAppsHeaderSearch !== null && rmRepoAppsHeaderSearch.value == '') {
    rmRepoAppsHeaderSearchInput.style.display = 'none'
}
function toggleSearch() {
    if (rmRepoAppsHeaderSearchInput.style.display == 'none') {
        rmRepoAppsHeaderSearchInput.style.display = 'block'
        return;
    }
    rmRepoAppsHeaderSearchInput.style.display = 'none'
}
