from django.urls import path

from .api import api

urlpatterns = [
    # path('upload/', FileUploadView.as_view(), name='file-upload'),
    # path('data-staging/', DataStagingView.as_view(), name='data-staging'),
    # path('meta-data/', CsvMetaDataView.as_view(), name='meta-data'),
    # path('fetch-data/', FetchDataFromCSV.as_view(), name='fetch-data'),
    # path('all-available-data-sources/', AllAvailableDataSources.as_view(), name='all-available-data-sources')
    path("data-staging/", api.urls)
]
