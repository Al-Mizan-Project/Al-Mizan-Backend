class AuditDatabaseRouter:
    """
    Routes database operations for:
    - ledger app  -> 'ledger' database
    - readstore   -> 'read' database
    - integrity   -> 'ledger' database (read-only)
    - everything else -> 'default'
    """

    LEDGER_APPS = {"ledger", "integrity"}
    READ_APPS = {"readstore"}

    def db_for_read(self, model, **hints):
        app_label = model._meta.app_label

        if app_label in self.LEDGER_APPS:
            return "ledger"

        if app_label in self.READ_APPS:
            return "read"

        return "default"

    def db_for_write(self, model, **hints):
        app_label = model._meta.app_label

        if app_label == "ledger":
            return "ledger"

        if app_label in {"readstore", "integrity"}:
            return None

        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations only within the same database group.
        """
        db_set = {"ledger", "read", "default"}

        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True

        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Control which apps migrate to which database.
        """

        if app_label == "ledger":
            return db == "ledger"

        if app_label == "readstore":
            return False

        if app_label == "integrity":
            return False

        return db == "default"