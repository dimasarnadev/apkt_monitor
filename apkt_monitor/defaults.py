DEFAULT_QUERY = """query getMonitoringKeluhanAll(
    $search: SearchWithDateArrayInput,
    $userId: BigInteger,
    $idUid: BigInteger,
    $idUlp: BigInteger
) {
    getMonitoringKeluhanAll(
        search: $search,
        userId: $userId,
        idUid: $idUid,
        idUlp: $idUlp
    ) {
        totalCount
        totalPage
        status
        message
        data {
            id
            no_laporan
            nama_pelapor
            permasalahan
            waktu_lapor
            waktu_batal
            waktu_selesai
            waktu_nyala
            durasi
            status_akhir
            alamat_pelanggan
            pelanggan_no_meter { no_meter nama id_pelanggan }
            master_ulp {
                id
                nama
                master_up3 { id nama }
            }
        }
    }
}"""

# Template Jinja. date_from/date_to = kemarin dan hari ini (timezone APKT Settings).
DEFAULT_VARIABLES = """{
  "search": {
    "skip": {{ skip }},
    "take": {{ take }},
    "sort": null,
    "requireTotalCount": true,
    "dateFrom": "{{ date_from }}",
    "dateTo": "{{ date_to }}",
    "isCreateDate": false,
    "filter": [
      {"field": "master_ulp.master_up3.id", "value": [{{ account.id_up3 }}]},
      {"field": "master_ulp.id", "value": [{{ account.id_ulp }}]}
    ]
  },
  "userId": {{ account.user_id }},
  "idUid": {{ account.id_uid }},
  "idUlp": {{ account.id_ulp }}
}"""
