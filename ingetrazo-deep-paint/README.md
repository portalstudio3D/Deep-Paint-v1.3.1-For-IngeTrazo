# Deep Paint for IngeTrazo 🎨

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![IngeTrazo](https://img.shields.io/badge/IngeTrazo-v0.5.8%2B-green.svg)](https://ingetrazo.com)
[![Version](https://img.shields.io/badge/Version-1.3.1-orange.svg)](https://github.com/YOUR_GITHUB_USERNAME/ingetrazo-deep-paint/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/YOUR_GITHUB_USERNAME/ingetrazo-deep-paint)

**Deep Paint** est une extension pour le logiciel de modélisation 3D **IngeTrazo**. Elle permet d'appliquer des matériaux, des couleurs et des textures directement sur n'importe quelle face située à l'intérieur d'un **Groupe** ou d'un **Composant**, **sans avoir besoin d'ouvrir ou d'éditer chaque conteneur**.

> *(An English version is available below)*

---

## 🇫🇷 Français

### 🎯 Le Problème Résolu
Dans les logiciels de CAO 3D traditionnels et dans IngeTrazo, pour peindre une face précise au sein d'un groupe ou d'un composant imbriqué, il faut généralement :
1. Sélectionner le conteneur.
2. Double-cliquer pour entrer dans le mode d'édition du groupe (souvent plusieurs fois si les conteneurs sont imbriqués).
3. Appliquer la couleur ou la texture.
4. Cliquer à l'extérieur pour refermer chaque conteneur.

**Deep Paint élimine toutes ces étapes** : vous survolez la face cible dans votre scène 3D, même enfouie dans une hiérarchie complexe de groupes, et vous cliquez pour peindre immédiatement !

---

### ✨ Fonctionnalités Principales

#### 1. 🗂️ Peinture en Profondeur (Deep Raycasting)
- **Détection géométrique directe** : le raycasting pénètre à travers les groupes et composants parents pour identifier la face exacte sous le curseur.
- **Mise en surbrillance en temps réel** : la face ciblée s'allume au survol pour garantir une précision absolue.

#### 2. ⚡ Synchronisation Automatique avec l'Outil Peinture Standard (`B`)
- Lorsque vous utilisez le pot de peinture standard (**`B`**) d'IngeTrazo et que vous prélevez une texture ou couleur avec la pipette (**`Alt + Clic`**), **Deep Paint la conserve automatiquement** !
- Activez Deep Paint pour appliquer directement cette matière au cœur de vos groupes.
- La synchronisation fonctionne également dans le sens inverse.

#### 3. 🖼️ Support Complet des Textures et Projections UV
- Gère fidèlement les textures images du projet (`.png`, `.jpg`), y compris leur échelle métrique (*Scale Width / Scale Height*) et leur orientation.
- Intègre les commandes natives de projection (`_texture_commands`) pour un rendu fluide et sans couture.

#### 4. 🧰 Barre d'Outils Native Dockable & Épurée
- Intégration dans la barre supérieure d'IngeTrazo (style MultiView).
- Deux boutons épurés :
  - **Deep Paint** : Bouton d'activation avec témoin d'état actif.
  - **Options** : Menu surgissant instantané pour configurer la portée de peinture, la pipette, la palette et parcourir les matériaux de votre scène.
- Déplaçable et détachable librement grâce à sa poignée.

#### 5. 🎯 4 Modes de Propagation Intelligents
- 🎯 **Face cliquée uniquement** : modifie uniquement la surface sous la souris.
- 🔗 **Faces similaires du groupe (`Shift + Clic`)** : applique la matière à toutes les faces du groupe partageant la même matière initiale.
- 📐 **Faces coplanaires connectées** : propage la matière sur toutes les faces adjacentes situées sur le même plan géométrique.
- 🧹 **Réinitialiser au défaut** : supprime la surcharge de matériau pour que la face réhérite de la matière globale du groupe.

#### 6. 🧪 Pipette Intégrée (Échantillonnage)
- Maintenez **`Alt`** et cliquez sur n'importe quelle face (même dans un groupe) pour capturer instantanément son matériau, sa texture et son échelle UV.

#### 7. 📱 Panneau Latéral 100% Responsive & Étroit
- S'intègre dans le plateau d'onglets latéral (*Propriétés, BIM, Calques, Deep Paint*).
- Conçu spécialement pour rester compact et fluide même sur des barres latérales très étroites (200px – 260px) sans jamais déborder ni écraser la vue 3D.
- Nuancier rapide en grille 6×2 et sélecteur de couleurs système.

#### 8. ↩️ Historique et Annulation Native (`Ctrl + Z`)
- Toutes les opérations de peinture sont enregistrées dans le gestionnaire d'historique transactionnel d'IngeTrazo (`CompoundCommand`).
- Annulez (`Ctrl + Z`) et rétablissez (`Ctrl + Y`) en toute sécurité.

---

### ⌨️ Raccourcis Utiles

| Action | Raccourci |
|---|---|
| **Activer Deep Paint** | `Ctrl + Shift + B` (ou clic sur l'icône dans la barre) |
| **Peindre la face ciblée** | `Clic gauche` |
| **Peindre toutes les faces similaires** | `Shift + Clic gauche` |
| **Pipette (capturer matière & texture)** | `Alt + Clic gauche` (ou `B` puis `Alt + Clic`) |
| **Annuler la dernière action** | `Ctrl + Z` |

---

### 📥 Installation

#### Option 1 : Installation Manuelle (Recommandée)
1. Téléchargez la dernière version depuis la page [Releases](https://github.com/YOUR_GITHUB_USERNAME/ingetrazo-deep-paint/releases).
2. Copiez le dossier `ingetrazo-deep-paint` (ou le fichier `deep_paint.py`) dans le répertoire des extensions d'IngeTrazo :
   - **Windows** : `%APPDATA%\IngeTrazo\plugins\deep_paint\`  
     *(Chemin complet : `C:\Users\<VotreNom>\AppData\Roaming\IngeTrazo\plugins\deep_paint\`)*
   - **Linux** : `~/.local/share/ingetrazo/plugins/deep_paint/`
   - **macOS** : `~/Library/Application Support/IngeTrazo/plugins/deep_paint/`
3. Lancez IngeTrazo : la barre d'outils **Deep Paint** apparaît en haut de l'écran.

#### Option 2 : Catalogue Officiel d'IngeTrazo
Dès que l'extension est validée dans le dépôt officiel [ingelibre/ingetrazo-extensions](https://github.com/ingelibre/ingetrazo-extensions), vous pourrez l'installer directement depuis le menu **Extensions ▸ Gérer les extensions...**.

---

<br>

---

## 🇬🇧 English

### 🎯 The Problem Solved
In traditional 3D CAD applications and IngeTrazo, painting an individual face inside a group or component usually requires:
1. Selecting the container.
2. Double-clicking multiple times into nested container edit modes.
3. Applying the material.
4. Clicking outside repeatedly to close all containers.

**Deep Paint eliminates these steps**: hover any face inside your model—no matter how deeply nested—and click to paint it instantly!

---

### ✨ Features (v1.3.1)

1. **Deep Raycast Painting**: Direct raycasting penetrates container hierarchies to target nested geometry.
2. **Paint Tool (B) Sync**: Pick any material/texture with the standard bucket tool (**`B`**) and eyedropper (**`Alt + Click`**); Deep Paint automatically preserves and uses it.
3. **Full Texture & UV Projection**: Accurately reproduces image textures with correct UV scaling and orientation.
4. **Clean Native Toolbar**: Minimal 2-button dockable `QToolBar` (Deep Paint toggle and Options menu).
5. **Propagation Modes**: Single Face, Similar Faces in Group (`Shift + Click`), Coplanar Connected Faces, and Reset Material.
6. **Built-in Eyedropper**: Sample materials and textures directly inside containers with `Alt + Click`.
7. **Narrow & Responsive Side Panel**: Fits seamlessly into IngeTrazo's side tray without forcing horizontal stretching.
8. **Native Undo/Redo**: Full transactional `Ctrl + Z` integration.

---

### ⌨️ Keybindings

| Action | Shortcut |
|---|---|
| **Toggle Deep Paint** | `Ctrl + Shift + B` |
| **Paint target face** | `Left Click` |
| **Paint similar faces in group** | `Shift + Left Click` |
| **Eyedropper sample** | `Alt + Left Click` |
| **Undo** | `Ctrl + Z` |

---

### 📄 License

Distribué sous licence **GPL-3.0-or-later**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.
IngeTrazo est développé par [IngeLibre](https://github.com/ingelibre).
