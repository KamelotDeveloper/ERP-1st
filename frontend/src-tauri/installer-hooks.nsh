!macro NSIS_HOOK_PREUNINSTALL
  ExecWait 'taskkill /f /im ga-erp-backend.exe'
!macroend
