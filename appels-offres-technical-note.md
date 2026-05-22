# Appels d'offres - notes techniques (2026-05-22)

Ce document explique comment utiliser le service Appels d'offres apres la refonte des regles metier.
Il est destine aux devs qui consomment cette API et doivent ajuster leurs integrations.

## TL;DR (changements a prendre en compte)

- `type_procedure` est maintenant normalise (publique/restreint/gre_a_gre/consultation).
- La validation est geree via `statut` (non_valide/valide/refuse/ferme).
- L execution du workflow est separee dans `etat_execution` (brouillon/publie/depot_cloture/plis_ouverts/annule).
- `commission_id` et `validated_by` sont des UUID string (peuvent etre null).
- Les regles par procedure imposent des documents et/ou operateurs invites/choisis.
- La consultation bypass la validation et force `statut=valide`, `commission_id=null`, `validation_level=aucun`.

## Champs cles

- `type_procedure` (obligatoire)
  - Valeurs cibles: `publique`, `restreint`, `gre_a_gre`, `consultation`
  - Alias acceptes en input (legacy): "Appel d'offres ouvert", "Appel d'offres restreint", "Consultation", "Gre a gre"
- `statut`: etat de validation (non_valide/valide/refuse/ferme)
- `etat_execution`: etat d execution (brouillon/publie/depot_cloture/plis_ouverts/annule)
- `commission_id`:
  - UUID string de `Organisation.id_organisation` (commission externe) ou `null` (commission interne)
- `validation_level`: `aucun`, `interne`, `externe_wilaya`, `externe_secteur`, `externe_nationale`
- `validated_by`: UUID string de `Membre.id_membre`, `null` si non valide
- Documents:
  - `id_doc_cdc` (CDC)
  - `id_doc_justification` (justif du choix)
  - `id_doc_besoin` (besoin)
- Operateurs:
  - `operateurs_invites[]`
  - `id_operateur_choisi`

## Regles par procedure

- publique
  - validation obligatoire
  - pas d invites obligatoires
  - execution autorisee
- restreint
  - validation obligatoire
  - `operateurs_invites` obligatoire
  - `id_doc_cdc` + `id_doc_justification` obligatoires
  - execution autorisee
- gre_a_gre
  - validation obligatoire
  - `id_operateur_choisi` obligatoire
  - `id_doc_cdc` + `id_doc_justification` obligatoires
  - force `date_limite_soumission`, `date_ouverture_plis`, `poids_technique`, `poids_financier` a null
  - execution interdite
- consultation
  - pas de validation (auto valide)
  - `id_operateur_choisi` obligatoire
  - `id_doc_besoin` obligatoire (pas de CDC)
  - force `date_limite_soumission`, `date_ouverture_plis`, `poids_technique`, `poids_financier` a null
  - execution interdite

## Routage de validation (seuils)

Les procedures qui requierent validation (publique, restreint, gre_a_gre) sont routees selon `montant_estime`:

1) Si `montant_estime > seuil_national` -> commission nationale
2) Sinon si `montant_estime > seuil_sectoriel` -> commission sectorielle (par secteur du service contractant)
3) Sinon si `montant_estime > seuil_wilaya` -> commission wilaya (par wilaya du service contractant)
4) Sinon -> commission interne (donc `commission_id=null`, `validation_level=interne`)

Source des seuils: `acteurs_service.CommissionExterne` avec `niveau_competence` et `seuil`.
Le routage utilise `Organisation.secteur` et `Organisation.wilaya` de la commission.

Important: sans commissions externes configurees, la creation ou soumission en validation echoue (400).

## Visibilite (querysets)

- Operateur economique:
  - voit uniquement les appels `statut=valide`
  - pour restreint/gre_a_gre/consultation: doit etre invite ou choisi
- Commission externe:
  - voit uniquement `statut=non_valide` avec `commission_id` correspondant
- Appel interne (commission_id null): pas visible pour commission externe
- Les appels internes (token X-Internal-Service-Token) bypass le filtrage

## Endpoints

CRUD:
- GET /appels-offres
- POST /appels-offres
- GET /appels-offres/<id>
- PUT/PATCH /appels-offres/<id>
- DELETE /appels-offres/<id>

Validation:
- POST /appels-offres/<id>/soumettre-validation
- POST /appels-offres/<id>/valider
- POST /appels-offres/<id>/refuser

Execution (publique + restreint seulement):
- POST /appels-offres/<id>/publier
- POST /appels-offres/<id>/cloturer-depot
- POST /appels-offres/<id>/ouvrir-plis
- POST /appels-offres/<id>/annuler

## Flux recommends

- Creation procedure validee (publique/restreint/gre_a_gre)
  1) POST /appels-offres
  2) POST /appels-offres/<id>/soumettre-validation
  3) POST /appels-offres/<id>/valider (ou /refuser)

- Execution (publique/restreint)
  1) verifier `statut=valide`
  2) POST /publier -> /cloturer-depot -> /ouvrir-plis
  3) /annuler possible avant `plis_ouverts`

- Consultation
  - creation directe -> `statut=valide`, `validation_level=aucun`, `commission_id=null`

## Erreurs frequentes

- 400 "Aucune commission nationale configuree": manque de commissions externes.
- 400 "Le secteur est obligatoire": `secteur` absent pour routage sectoriel.
- 400 "Le document de besoin est obligatoire": consultation sans `id_doc_besoin`.
- 400 "L appel doit etre valide": tentative d execution avant validation.

## Migration

Appliquer la migration Appels d offres apres pull:

- python manage.py migrate

## Script de test

Un script bash est disponible pour tester les scenarios:

- backend/scripts/test_appels_offres_workflow.sh
