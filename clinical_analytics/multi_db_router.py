class MultiDBRouter:
    def db_for_read(self, model, **hints):
        """Directs read operations for specific models to their respective databases."""
        print("MultiDBRouter :" + model._meta.model_name)
        if hasattr(model._meta, 'mongodb_model') and model._meta.mongodb_model:
            return 'mongo_db'
        return 'default'

    def db_for_write(self, model, **hints):
        """Directs write operations for specific models to their respective databases."""
        return self.db_for_read(model, **hints)

    # def allow_relation(self, obj1, obj2, **hints):
    #     """Allows any relation if both models are from the same database."""
    #     if obj1._state.db == obj2._state.db:
    #         return True
    #     return None
    #
    # def allow_migrate(self, db, app_label, model_name=None, **hints):
    #     """Ensures that the 'MongoDbClient' model only appears in the 'mongo_db' database."""
    #     if db == 'mongo_db':
    #         return model_name == 'mongodbclient'
    #     elif model_name == 'mongodbclient':
    #         return False
    #     return None
