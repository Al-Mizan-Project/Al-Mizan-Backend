from abc import ABC, abstractmethod


class RecoursRepository(ABC):

    @abstractmethod
    def save(self, recours):
        pass

    @abstractmethod
    def get_by_id(self, recours_id: int):
        pass

    @abstractmethod
    def get_by_soumission(self, soumission_id: int):
        pass

    @abstractmethod
    def list(self, filters: dict):
        pass

    @abstractmethod
    def delete(self, recours_id: int):
        pass