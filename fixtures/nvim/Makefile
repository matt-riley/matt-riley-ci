.PHONY: docs

docs:
	@mkdir -p doc
	nvim --headless -u NONE \
		-c 'lua vim.opt.runtimepath:prepend(vim.fn.getcwd())' \
		-c 'lua vim.opt.runtimepath:append(vim.env.MINI_PATH)' \
		-c 'lua require("mini.doc").setup({})' \
		-c 'lua require("mini.doc").generate({ "lua/fixture.lua" }, "doc/fixture.txt")' \
		-c 'qa'
