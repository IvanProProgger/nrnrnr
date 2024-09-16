INITIATOR = {
    "initiator_to_head": (
        "Вы добавили новый счет №{row_id}.\nСчет передан на согласование руководителю департамента.\n"
        "{record_data_text}"
    ),
    "head_to_finance": (
        "Счет №{row_id} одобрен руководителем департамента {approver} и передан на согласование в финансовый отдел.\n"
        "{record_data_text}"
    ),
    "head_to_payment": (
        "Счет №{row_id} согласован руководителем департамента: {approver} и передан на оплату.\n{record_data_text}"
    ),
    "head_finance_to_payment": (
        "Счет №{row_id} согласован руководителем департамента и сотрудником финансового отдела: {approver} "
        "и передан на оплату.\n{record_data_text}"
    ),
    "paid": "Счет №{row_id} оплачен {approver}.\n{record_data_text}",
    "rejected": "Счет №{row_id} отклонен {approver}.\n{record_data_text}",
}

HEAD = {
    "from_initiator": (
        "Добавлен новый счет №{row_id} от {initiator_nickname}.\nПожалуйста, одобрите счет.\n{record_data_text}"
    ),
    "head_to_finance": (
        "Вы одобрили счет №{row_id}.\nСчет передан на согласование в финансовый отдел.\n{record_data_text}"
    ),
    "head_to_payment": (
        "Вы согласовали счет №{row_id}.\nСчет передан на оплату.\n{record_data_text}"
    ),
    "head_finance_to_payment": (
        "Счет №{row_id} согласован вами и сотрудником финансового отдела: {approver}.\n"
        "Счет передан на оплату.\n{record_data_text}"
    ),
    "paid": "Счет №{row_id} оплачен {approver}.\n{record_data_text}",
    "rejected": "Счет №{row_id} отклонен {approver}.\n{record_data_text}",
}

FINANCE = {
    "from_head": (
        "Добавлен новый счет №{row_id} от {initiator_nickname}\n"
        "Счет согласован руководителем департамента: {approver}.\n"
        "Пожалуйста, одобрите счет.\n{record_data_text}"
    ),
    "to_payment": (
        "Счет №{row_id} согласован вами и руководителем департамента: {approver}.\n"
        "Счет передан на оплату.\n{record_data_text}"
    ),
    "paid": "Счет №{row_id} оплачен {approver}.\n{record_data_text}",
    "rejected": "Счет №{row_id} отклонен {approver}.\n{record_data_text}",
}

PAYMENT = {
    "head_to_payment": (
        "Добавлен новый счет №{row_id} от {initiator_nickname}\nСчет согласован руководителем департамента: {approver}"
        " и готов к оплате.\nПожалуйста, оплатите счет.\n{record_data_text}"
    ),
    "finance_to_payment": (
        "Добавлен новый счет №{row_id} от {initiator_nickname}\nСчет согласован руководителем департамента и"
        " сотрудником финансового отдела: {approver}, и готов к оплате.\nПожалуйста, оплатите счет.\n"
        "{record_data_text}"
    ),
    "paid": "Счет №{row_id} оплачен {approver}.\n{record_data_text}",
    "rejected": "Счет №{row_id} отклонен {approver}.\n{record_data_text}",
}
