#!/usr/bin/env bash
set -e
shopt -s extglob

NODE=node_modules

set -x

# compile translations
python3 manage.py compilemessages

# update npm packages
npm install

# dialog-polyfill remove unused files
rm -rf ${NODE}/dialog-polyfill/!(dialog-polyfill.*)

# material-design-icons-iconfont remove unused files
rm -rf ${NODE}/material-design-icons-iconfont/!(dist)
rm -rf ${NODE}/material-design-icons-iconfont/.idea

# material-design-lite remove unused files
rm -rf ${NODE}/material-design-lite/!(dist|src|material.min.js)
rm -rf ${NODE}/material-design-lite/dist/!(images)
rm -rf ${NODE}/material-design-lite/.[tj]*

# roboto-fontface remove unused files
rm -rf ${NODE}/roboto-fontface/!(css|fonts)
rm -rf ${NODE}/roboto-fontface/.npmignore

# tinymce remove unused files
rm -rf ${NODE}/tinymce/!(plugins|skins|themes|tinymce.min.js|tinymce.js)
rm -rf ${NODE}/tinymce/themes/!(modern)
rm -rf ${NODE}/tinymce/plugins/!(autolink|link|lists)

# compile stylesheets
python3 manage.py compilescss

# rename folders so they can be ignored
mv ${NODE}/material-design-lite/src ${NODE}/material-design-lite/src-ignore
mv ${NODE}/roboto-fontface/css ${NODE}/roboto-fontface/css-ignore

# copy static files into STATIC_DIR
python3 manage.py collectstatic --no-input \
    -i *.scss -i *.less \
    -i tiny_mce \
    -i src-ignore \
    -i css-ignore \
    --clear

# rename folders back
mv ${NODE}/material-design-lite/src-ignore ${NODE}/material-design-lite/src
mv ${NODE}/roboto-fontface/css-ignore ${NODE}/roboto-fontface/css

echo "Ready to ship release!"