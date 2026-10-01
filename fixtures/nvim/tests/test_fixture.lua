local test = MiniTest.new_set()
test["loads consumer module"] = function()
	MiniTest.expect.equality(require("fixture").value, 42)
end
return test
