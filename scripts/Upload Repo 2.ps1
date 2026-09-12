# Navighează la directorul sursă
cd "d:\Teste cursor\remote-bat-runner"

# Inițializează git (dacă nu e deja)
git init

# Configurează remote
git remote remove origin 2>$null
git remote add origin https://github.com/me-suzy/Remote-bat-runner-2.git

# Adaugă toate fișierele
git add .

# Commit
git commit -m "Initial commit: Complete remote-bat-runner setup"

# Push (probabil pe main)
git push -u origin main -f

# Dacă nu merge, încearcă cu master
# git push -u origin master -f