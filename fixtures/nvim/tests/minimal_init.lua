vim.opt.rtp:append(os.getenv("MINI_PATH"))
vim.opt.rtp:append(vim.fn.getcwd())
require("mini.test").setup()
