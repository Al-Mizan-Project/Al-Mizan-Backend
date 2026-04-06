from django.urls import path

from .views import (
    CommissionEvaluationListCreateView,
    CommissionEvaluationMembreDetailView,
    CommissionEvaluationMembresView,
    CommissionEvaluationRetrieveUpdateDeleteView,
    CommissionExterneListCreateView,
    CommissionExterneRetrieveUpdateDeleteView,
    CommissionInterneListCreateView,
    CommissionInterneMembreDetailView,
    CommissionInterneMembresView,
    CommissionInterneRetrieveUpdateDeleteView,
    ServiceContractantCommissionsView,
    ServiceContractantCreateView,
    ServiceContractantMembresView,
    ServiceContractantRetrieveUpdateDeleteView,
)

urlpatterns = [
    # Commission Evaluation
    path("commissions-evaluation", CommissionEvaluationListCreateView.as_view()),
    path("commissions-evaluation/<int:commission_id>", CommissionEvaluationRetrieveUpdateDeleteView.as_view()),
    path("commissions-evaluation/<int:commission_id>/membres", CommissionEvaluationMembresView.as_view()),
    path("commissions-evaluation/<int:commission_id>/membres/<int:membre_id>", CommissionEvaluationMembreDetailView.as_view()),
    # Commission Interne
    path("commissions-internes", CommissionInterneListCreateView.as_view()),
    path("commissions-internes/<int:commission_interne_id>", CommissionInterneRetrieveUpdateDeleteView.as_view()),
    path("commissions-internes/<int:commission_interne_id>/membres", CommissionInterneMembresView.as_view()),
    path("commissions-internes/<int:commission_interne_id>/membres/<int:membre_id>", CommissionInterneMembreDetailView.as_view()),
    # Service Contractant
    path("services-contractants", ServiceContractantCreateView.as_view()),
    path("services-contractants/<int:service_id>", ServiceContractantRetrieveUpdateDeleteView.as_view()),
    path("services-contractants/<int:service_id>/membres", ServiceContractantMembresView.as_view()),
    path("services-contractants/<int:service_id>/commissions", ServiceContractantCommissionsView.as_view()),
    # Commission Externe
    path("commissions-externes", CommissionExterneListCreateView.as_view()),
    path("commissions-externes/<int:commission_externe_id>", CommissionExterneRetrieveUpdateDeleteView.as_view()),
]
