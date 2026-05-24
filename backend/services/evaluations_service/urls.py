from django.urls import path
from .views import (
    HealthView,
    CommissionDetailView,
    RegistreReceptionListView, ConfirmerIntegriteView,
    SeanceOuvertureView, DemarrerSeanceView, CloturerSeanceView,
    OuvrirPliView, ParapherPliView,
    ConformiteView,
    CapacitesView,
    EvalTechniqueView, LockEvalTechniqueView,
    EvalFinanciereView, LockEvalFinanciereView,
    ClassementView, CalculerClassementView, EcarterProvisionalView,
    PVView, SignerPVView, LockPVView,
    SoumettreAuSCView, SCDecisionView,
    # Legacy
    EvaluationView, EvaluationDetailView,
)

urlpatterns = [
    path('health', HealthView.as_view()),

    # Commission
    path('commissions/<int:id_comission>/', CommissionDetailView.as_view()),

    # Step 1 — Registre
    path('commissions/<int:id_comission>/registre/', RegistreReceptionListView.as_view()),
    path('commissions/<int:id_comission>/registre/confirmer-integrite/', ConfirmerIntegriteView.as_view()),

    # Step 2 — Séance ouverture
    path('commissions/<int:id_comission>/seance/', SeanceOuvertureView.as_view()),
    path('commissions/<int:id_comission>/seance/demarrer/', DemarrerSeanceView.as_view()),
    path('commissions/<int:id_comission>/seance/cloturer/', CloturerSeanceView.as_view()),
    path('commissions/<int:id_comission>/seance/ouvrir-pli/', OuvrirPliView.as_view()),
    path('commissions/<int:id_comission>/seance/plis/<int:id_soumission>/parapher/', ParapherPliView.as_view()),

    # Step 3 — Conformité
    path('commissions/<int:id_comission>/conformite/', ConformiteView.as_view()),

    # Step 4 — Capacités
    path('commissions/<int:id_comission>/capacites/', CapacitesView.as_view()),

    # Step 5 — Évaluation technique
    path('commissions/<int:id_comission>/eval-technique/', EvalTechniqueView.as_view()),
    path('commissions/<int:id_comission>/eval-technique/lock/', LockEvalTechniqueView.as_view()),

    # Step 6 — Évaluation financière
    path('commissions/<int:id_comission>/eval-financiere/', EvalFinanciereView.as_view()),
    path('commissions/<int:id_comission>/eval-financiere/lock/', LockEvalFinanciereView.as_view()),

    # Step 7 — Classement
    path('commissions/<int:id_comission>/classement/', ClassementView.as_view()),
    path('commissions/<int:id_comission>/classement/calculer/', CalculerClassementView.as_view()),
    path('commissions/<int:id_comission>/classement/ecarter-provisional/', EcarterProvisionalView.as_view()),

    # Step 8 — PV
    path('commissions/<int:id_comission>/pv/<str:type_pv>/', PVView.as_view()),
    path('commissions/<int:id_comission>/pv/<str:type_pv>/signer/', SignerPVView.as_view()),
    path('commissions/<int:id_comission>/pv/<str:type_pv>/verrouiller/', LockPVView.as_view()),
    path('commissions/<int:id_comission>/soumettre-sc/', SoumettreAuSCView.as_view()),
    path('commissions/<int:id_comission>/sc-decision/', SCDecisionView.as_view()),

    # Legacy — kept for backward compat
    path('evaluations', EvaluationView.as_view(), name='evaluations'),
    path('evaluations/<int:evaluation_id>', EvaluationDetailView.as_view(), name='evaluation_detail'),
]