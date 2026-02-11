from pgvector.django import VectorField

class SafeVectorField(VectorField):
    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return super().db_type(connection)
        return 'text'
