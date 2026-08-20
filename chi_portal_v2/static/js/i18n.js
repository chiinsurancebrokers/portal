/**
 * CHI Insurance Portal — Client Trilingual UI
 * Languages: el (Greek) · en (English) · zh (Chinese Simplified)
 * Usage: add data-i18n="key" to any element; text content is replaced on lang switch.
 *        data-i18n-placeholder="key" for input placeholders.
 *        data-i18n-title="key" for title attributes.
 */

const I18N = {
  el: {
    /* ── NAV / SIDEBAR ─────────────────────────────── */
    nav_home:        "Αρχική",
    nav_policies:    "Ασφαλιστήριά μου",
    nav_documents:   "Έγγραφα",
    nav_hal:         "HAL Assistant",
    nav_settings:    "Ρυθμίσεις",
    nav_logout:      "Αποσύνδεση",
    nav_client_portal: "👤 Client Portal",

    /* ── DASHBOARD ─────────────────────────────────── */
    dash_active_policies:  "Ενεργά Συμβόλαια",
    dash_next_payment:     "Επόμενη Πληρωμή",
    dash_expiring_30:      "Λήγουν σε 30 ημέρες",
    dash_my_policies:      "Τα Ασφαλιστήριά μου",
    dash_see_all:          "Δείτε Όλα",
    dash_no_policies:      "Δεν υπάρχουν ενεργά συμβόλαια",
    dash_hal_title:        "HAL — Ο Ασφαλιστικός Σας Σύμβουλος",
    dash_hal_desc:         "Έχετε ερωτήσεις για τα ασφαλιστήριά σας; Ο HAL μπορεί να σας εξηγήσει τις καλύψεις, τις εξαιρέσεις, και τι να κάνετε σε περίπτωση ατυχήματος.",
    dash_hal_btn:          "Ρωτήστε τον HAL",
    dash_my_docs:          "Έγγραφά μου",
    dash_no_docs:          "Δεν υπάρχουν έγγραφα",
    dash_manage_docs:      "Διαχείριση Εγγράφων",
    dash_expiry_alert:     "Επείγον: Λήξη Ασφαλιστηρίων",
    dash_expiry_contact:   "Επικοινωνήστε μαζί μας:",
    dash_expires:          "λήγει",
    dash_welcome:          "Καλώς ήρθατε,",

    /* ── POLICIES ──────────────────────────────────── */
    pol_title:             "Τα Ασφαλιστήριά μου",
    pol_no_policies:       "Δεν υπάρχουν ασφαλιστήρια",
    pol_start:             "ΕΝΑΡΞΗ",
    pol_expiry:            "ΛΗΞΗ",
    pol_next_payment:      "ΕΠΟΜΕΝΗ ΠΛΗΡΩΜΗ",
    pol_coverages:         "ΚΑΛΥΨΕΙΣ",
    pol_payment_history:   "Ιστορικό Πληρωμών",
    pol_due_date:          "Ημ. Λήξης",
    pol_amount:            "Ποσό",
    pol_status:            "Κατάσταση",
    pol_paid_on:           "Πληρώθηκε",
    pol_days:              "ημ.",

    /* ── DOCUMENTS ─────────────────────────────────── */
    doc_title:             "Έγγραφά μου",
    doc_upload_title:      "Ανέβασμα Εγγράφου",
    doc_type_label:        "Τύπος Εγγράφου",
    doc_type_general:      "Γενικό Έγγραφο",
    doc_type_claim:        "Αξίωση / Ζημιά",
    doc_file_label:        "Αρχείο",
    doc_file_hint:         "PDF, JPG, PNG, DOCX · Μέγ. 16MB",
    doc_policy_label:      "Σχετικό Συμβόλαιο",
    doc_policy_general:    "— Γενικό Έγγραφο —",
    doc_message_label:     "Μήνυμα (προαιρετικό)",
    doc_message_ph:        "π.χ. περιγραφή ζημιάς, διευκρίνιση...",
    doc_upload_btn:        "Ανέβασμα",
    doc_list_title:        "Έγγραφά μου",
    doc_download:          "Λήψη",
    doc_no_docs:           "Δεν υπάρχουν έγγραφα",

    /* ── HAL ───────────────────────────────────────── */
    hal_title:             "HAL — AI Ασφαλιστικός Σύμβουλος",
    hal_my_policies:       "Τα Συμβόλαιά μου",
    hal_knows:             "Ο HAL γνωρίζει τα ασφαλιστήριά σας και μπορεί να απαντήσει σε ερωτήσεις.",
    hal_questions:         "Ερωτήσεις για τον HAL",
    hal_q1:                "Τι καλύπτουν τα συμβόλαιά μου;",
    hal_q2:                "Πότε λήγει κάθε συμβόλαιό μου;",
    hal_q3:                "Ποιες είναι οι εξαιρέσεις;",
    hal_q4:                "Πώς υποβάλλω μια αξίωση;",
    hal_greeting:          "Γεια σας! Είμαι ο HAL, ο AI ασφαλιστικός σύμβουλος της CHI Insurance Brokers. Μπορώ να σας εξηγήσω τις καλύψεις όλων των ασφαλιστηρίων σας — αυτοκίνητο, ζωή, υγεία, περιουσία, ταξίδι, κατοικίδια ή επιχείρηση — τι κάνετε σε περίπτωση ζημιάς ή ατυχήματος, ή οποιαδήποτε άλλη ερώτηση. Πώς μπορώ να σας βοηθήσω;",
    hal_placeholder:       "Γράψτε την ερώτησή σας...",
    hal_expires:           "λήγει",
    hal_you:               "Εσείς:",
    hal_name:              "HAL:",
  },

  en: {
    /* ── NAV / SIDEBAR ─────────────────────────────── */
    nav_home:        "Home",
    nav_policies:    "My Policies",
    nav_documents:   "Documents",
    nav_hal:         "HAL Assistant",
    nav_settings:    "Settings",
    nav_logout:      "Sign Out",
    nav_client_portal: "👤 Client Portal",

    /* ── DASHBOARD ─────────────────────────────────── */
    dash_active_policies:  "Active Policies",
    dash_next_payment:     "Next Payment",
    dash_expiring_30:      "Expiring in 30 days",
    dash_my_policies:      "My Policies",
    dash_see_all:          "View All",
    dash_no_policies:      "No active policies",
    dash_hal_title:        "HAL — Your Insurance Advisor",
    dash_hal_desc:         "Have questions about your insurance? HAL can explain your coverages, exclusions, and what to do in case of an accident.",
    dash_hal_btn:          "Ask HAL",
    dash_my_docs:          "My Documents",
    dash_no_docs:          "No documents",
    dash_manage_docs:      "Manage Documents",
    dash_expiry_alert:     "Urgent: Policy Expiry",
    dash_expiry_contact:   "Contact us:",
    dash_expires:          "expires",
    dash_welcome:          "Welcome,",

    /* ── POLICIES ──────────────────────────────────── */
    pol_title:             "My Policies",
    pol_no_policies:       "No policies found",
    pol_start:             "START",
    pol_expiry:            "EXPIRY",
    pol_next_payment:      "NEXT PAYMENT",
    pol_coverages:         "COVERAGES",
    pol_payment_history:   "Payment History",
    pol_due_date:          "Due Date",
    pol_amount:            "Amount",
    pol_status:            "Status",
    pol_paid_on:           "Paid On",
    pol_days:              "days",

    /* ── DOCUMENTS ─────────────────────────────────── */
    doc_title:             "My Documents",
    doc_upload_title:      "Upload Document",
    doc_type_label:        "Document Type",
    doc_type_general:      "General Document",
    doc_type_claim:        "Claim / Damage",
    doc_file_label:        "File",
    doc_file_hint:         "PDF, JPG, PNG, DOCX · Max 16MB",
    doc_policy_label:      "Related Policy",
    doc_policy_general:    "— General Document —",
    doc_message_label:     "Message (optional)",
    doc_message_ph:        "e.g. damage description, clarification...",
    doc_upload_btn:        "Upload",
    doc_list_title:        "My Documents",
    doc_download:          "Download",
    doc_no_docs:           "No documents",

    /* ── HAL ───────────────────────────────────────── */
    hal_title:             "HAL — AI Insurance Advisor",
    hal_my_policies:       "My Policies",
    hal_knows:             "HAL knows your policies and can answer your questions.",
    hal_questions:         "Questions for HAL",
    hal_q1:                "What do my policies cover?",
    hal_q2:                "When does each policy expire?",
    hal_q3:                "What are the exclusions?",
    hal_q4:                "How do I file a claim?",
    hal_greeting:          "Hello! I'm HAL, the AI insurance advisor of CHI Insurance Brokers. I can explain the coverages of all your policies — car, life, health, property, travel, pets or business — what to do in case of damage or an accident, or any other question. How can I help you?",
    hal_placeholder:       "Type your question...",
    hal_expires:           "expires",
    hal_you:               "You:",
    hal_name:              "HAL:",
  },

  zh: {
    /* ── NAV / SIDEBAR ─────────────────────────────── */
    nav_home:        "主页",
    nav_policies:    "我的保单",
    nav_documents:   "文件",
    nav_hal:         "HAL 助手",
    nav_settings:    "设置",
    nav_logout:      "退出登录",
    nav_client_portal: "👤 客户门户",

    /* ── DASHBOARD ─────────────────────────────────── */
    dash_active_policies:  "有效保单",
    dash_next_payment:     "下次付款",
    dash_expiring_30:      "30天内到期",
    dash_my_policies:      "我的保单",
    dash_see_all:          "查看全部",
    dash_no_policies:      "暂无有效保单",
    dash_hal_title:        "HAL — 您的保险顾问",
    dash_hal_desc:         "对您的保险有疑问？HAL 可以解释您的保障范围、除外责任，以及发生事故时应该怎么做。",
    dash_hal_btn:          "咨询 HAL",
    dash_my_docs:          "我的文件",
    dash_no_docs:          "暂无文件",
    dash_manage_docs:      "管理文件",
    dash_expiry_alert:     "紧急：保单即将到期",
    dash_expiry_contact:   "请联系我们：",
    dash_expires:          "到期",
    dash_welcome:          "欢迎，",

    /* ── POLICIES ──────────────────────────────────── */
    pol_title:             "我的保单",
    pol_no_policies:       "暂无保单",
    pol_start:             "生效日期",
    pol_expiry:            "到期日期",
    pol_next_payment:      "下次付款",
    pol_coverages:         "保障范围",
    pol_payment_history:   "付款记录",
    pol_due_date:          "到期日",
    pol_amount:            "金额",
    pol_status:            "状态",
    pol_paid_on:           "付款日期",
    pol_days:              "天",

    /* ── DOCUMENTS ─────────────────────────────────── */
    doc_title:             "我的文件",
    doc_upload_title:      "上传文件",
    doc_type_label:        "文件类型",
    doc_type_general:      "一般文件",
    doc_type_claim:        "理赔 / 损失",
    doc_file_label:        "文件",
    doc_file_hint:         "PDF、JPG、PNG、DOCX · 最大 16MB",
    doc_policy_label:      "相关保单",
    doc_policy_general:    "— 一般文件 —",
    doc_message_label:     "留言（可选）",
    doc_message_ph:        "例如：损失描述、说明...",
    doc_upload_btn:        "上传",
    doc_list_title:        "我的文件",
    doc_download:          "下载",
    doc_no_docs:           "暂无文件",

    /* ── HAL ───────────────────────────────────────── */
    hal_title:             "HAL — AI 保险顾问",
    hal_my_policies:       "我的保单",
    hal_knows:             "HAL 了解您的保单，可以回答您的问题。",
    hal_questions:         "向 HAL 提问",
    hal_q1:                "我的保单涵盖哪些内容？",
    hal_q2:                "每份保单何时到期？",
    hal_q3:                "有哪些除外责任？",
    hal_q4:                "如何提交理赔申请？",
    hal_greeting:          "您好！我是 HAL，CHI 保险经纪公司的 AI 保险顾问。我可以为您解释所有保单的保障范围——汽车、人寿、健康、财产、旅行、宠物或商业保险——以及发生损失或事故时应该怎么做，或回答任何其他问题。我能为您提供什么帮助？",
    hal_placeholder:       "输入您的问题...",
    hal_expires:           "到期",
    hal_you:               "您：",
    hal_name:              "HAL：",
  }
};

/* ── LANGUAGE SWITCHER ENGINE ──────────────────────────────────────────────── */

const LANG_KEY = 'chi_lang';
const LANG_FLAGS = { el: '🇬🇷', en: '🇬🇧', zh: '🇨🇳' };
const LANG_LABELS = { el: 'ΕΛ', en: 'EN', zh: '中文' };

function getLang() {
  return localStorage.getItem(LANG_KEY) || 'el';
}

function setLang(lang) {
  localStorage.setItem(LANG_KEY, lang);
  applyLang(lang);
  updateToggleUI(lang);
}

function t(key) {
  const lang = getLang();
  return (I18N[lang] && I18N[lang][key]) || (I18N['el'][key]) || key;
}

function applyLang(lang) {
  const dict = I18N[lang] || I18N['el'];

  // data-i18n → textContent
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] !== undefined) el.textContent = dict[key];
  });

  // data-i18n-html → innerHTML (for elements with icons etc.)
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const key = el.getAttribute('data-i18n-html');
    if (dict[key] !== undefined) {
      // Preserve any leading <i> icon tags before the text
      const icon = el.querySelector('i');
      if (icon) {
        el.innerHTML = icon.outerHTML + ' ' + dict[key];
      } else {
        el.textContent = dict[key];
      }
    }
  });

  // data-i18n-placeholder → placeholder attribute
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (dict[key] !== undefined) el.placeholder = dict[key];
  });

  // data-i18n-title → title attribute
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    if (dict[key] !== undefined) el.title = dict[key];
  });

  // Update <html lang> attribute
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
}

function updateToggleUI(lang) {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === lang);
  });
}

function buildLangToggle() {
  // Only show for client role (the toggle div will only be injected in client pages)
  const container = document.getElementById('lang-toggle');
  if (!container) return;

  container.innerHTML = Object.keys(LANG_FLAGS).map(lang => `
    <button class="lang-btn ${getLang() === lang ? 'active' : ''}"
            data-lang="${lang}"
            onclick="setLang('${lang}')"
            title="${LANG_LABELS[lang]}">
      <span class="lang-flag">${LANG_FLAGS[lang]}</span>
      <span class="lang-label">${LANG_LABELS[lang]}</span>
    </button>
  `).join('');
}

// Auto-init on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  buildLangToggle();
  applyLang(getLang());
});

