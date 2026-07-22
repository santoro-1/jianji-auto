---@class T1608802625400681067 : ScriptComponent
----@field curTime number [UI(Range={0, 3}, Slider)]
----@field duration number [UI(Input)]
----@field time1 Vector2f
----@field PosRange1 Vector4f
----@field bezierParams1 Vector4f
----@field time2 Vector2f
----@field PosRange2 Vector4f
----@field bezierParams2 Vector4f
----@field time3 Vector2f
----@field PosRange3 Vector4f
----@field bezierParams3 Vector4f
----@field time4 Vector2f
----@field PosRange4 Vector4f
----@field bezierParams4 Vector4f
----@field extraSize number
----@field isAutoPlay boolean
local function getBezierValue(controls, t)
	local ret = {}
	local xc1 = controls[1]
	local yc1 = controls[2]
	local xc2 = controls[3]
	local yc2 = controls[4]
	ret[1] = 3 * xc1 * (1 - t) * (1 - t) * t + 3 * xc2 * (1 - t) * t * t + t * t * t
	ret[2] = 3 * yc1 * (1 - t) * (1 - t) * t + 3 * yc2 * (1 - t) * t * t + t * t * t
	return ret
end

local function getBezierDerivative(controls, t)
	local ret = {}
	local xc1 = controls[1]
	local yc1 = controls[2]
	local xc2 = controls[3]
	local yc2 = controls[4]
	ret[1] = 3 * xc1 * (1 - t) * (1 - 3 * t) + 3 * xc2 * (2 - 3 * t) * t + 3 * t * t
	ret[2] = 3 * yc1 * (1 - t) * (1 - 3 * t) + 3 * yc2 * (2 - 3 * t) * t + 3 * t * t
	return ret
end

local function getBezierTfromX(controls, x)
	local ts = 0
	local te = 1
	-- divide and conque
	repeat
		local tm = (ts + te) / 2
		local value = getBezierValue(controls, tm)
		if (value[1] > x) then
			te = tm
		else
			ts = tm
		end
	until (te - ts < 0.0001)

	return (te + ts) / 2
end

local function bezier(controls)
	return function(t, b, c, d)
		t = t / d
		local tvalue = getBezierTfromX(controls, t)
		local value = getBezierValue(controls, tvalue)
		return b + c * value[2]
		-- return 1 - (1 - t) * (1 - t);
	end
end

local function funcEaseBlurAction1(t, b, c, d)
	t = t / d
	-- diyijieduandeweiyiquxian，beisaierquxianbanben
	local controls = {.05, .71, .61, .99}
	local tvalue = getBezierTfromX(controls, t)
	local deriva = getBezierDerivative(controls, tvalue)
	return math.abs(deriva[2] / deriva[1]) * c
end

local function funcEaseAction3(t, b, c, d)
	t = t / d
	-- diyijieduandeweiyiquxian，zhegeshigongshibanben
	if t ~= 0.0 and t ~= 1.0 then
		t = math.exp(-7.0 * t) * 1.0 * math.sin((t - 0.075) * (2.0 * math.pi) / 0.3) + 1.0
	end
	return Amaz.Ease.linearFunc(t, c, b)
end

local function funcEaseBlurAction3(t, b, c, d)
	t = t / d
	-- diyijieduandemohuquxian，zhegeshigongshibanben
	t =
		math.abs(
		math.pow(2, -5.0 * t) * math.log(2) * math.sin(2.5 * math.pi * t - 0.5 * math.pi) +
			math.pow(2, -5.0 * t) * math.cos(2.5 * math.pi * t - 0.5 * math.pi)
	)

	return c * t
end

local function clamp(min, max, value)
	return math.min(math.max(value, 0), 1)
end

local function saturate(value)
	return clamp(0, 1, value)
end

local function lerp(a, b, c)
	c = saturate(0, 1, c)
	return (1 - c) * a + c * b
end

local function lerpVector3(a, b, c)
	c = saturate(0, 1, c)
	return Amaz.Vector3f(lerp(a.x, b.x, c), lerp(a.y, b.y, c), lerp(a.z, b.z, c))
end

local function remap(smin, smax, dmin, dmax, value)
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

local function remapClamped(smin, smax, dmin, dmax, value)
	return saturate(value - smin) / (smax - smin) * (dmax - dmin) + dmin
end

local function remapVector3(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z)
	)
end

local function remapVector4(smin, smax, dmin, dmax, value)
	return Amaz.Vector3f(
		remap(smin.x, smax.x, dmin.x, dmax.x, value.x),
		remap(smin.y, smax.y, dmin.y, dmax.y, value.y),
		remap(smin.z, smax.z, dmin.z, dmax.z, value.z),
		remap(smin.w, smax.w, dmin.w, dmax.w, value.w)
	)
end

local exports = exports or {}
local T1608802625400681067 = T1608802625400681067 or {}
T1608802625400681067.__index = T1608802625400681067
function T1608802625400681067.new(construct, ...)
	local self = setmetatable({}, T1608802625400681067)
	self.duration = 1.0
	self.curTime = 0
	self.count = 0
	if construct and T1608802625400681067.constructor then
		T1608802625400681067.constructor(self, ...)
	end
	return self
end

function T1608802625400681067:constructor()
end

local renderChain = {
	{
		name = "pass1",
		input = {},
		shader_vs_path = "shader/pass1/vs.lua",
		shader_fs_path = "shader/pass1/fs.lua",
		blendEnable = true
	}
	-- {
	--     name = "pass2",
	--     input = {
	--         pass2_inputTex_0 = "pass1",
	--     },
	--     shader_vs_path = "shader/pass2/vs.lua",
	--     shader_fs_path = "shader/pass2/fs.lua",
	-- 	blendEnable = false
	-- },
	-- {
	--     name = "pass3",
	--     input = {
	--         pass3_inputTex_0 = "pass2",
	--     },
	--     shader_vs_path = "shader/pass3/vs.lua",
	--     shader_fs_path = "shader/pass3/fs.lua",
	-- 	blendEnable = false
	-- },
	-- {
	--     name = "pass4",
	--     input = {
	--         pass4_inputTex_0 = "pass3",
	-- 		pass4_inputTex_1 = "pass2"
	--     },
	--     shader_vs_path = "shader/pass4/vs.lua",
	--     shader_fs_path = "shader/pass4/fs.lua",
	-- 	blendEnable = false
	-- },
	-- {
	--     name = "pass5",
	--     input = {
	--         pass5_inputTex_0 = "pass4",
	--     },
	--     shader_vs_path = "shader/pass5/vs.lua",
	--     shader_fs_path = "shader/pass5/fs.lua",
	-- 	blendEnable = false
	-- },
	-- {
	--     name = "pass6",
	--     input = {
	--         pass6_inputTex_0 = "pass5",
	-- 		pass6_inputTex_1 = "pass4"
	--     },
	--     shader_vs_path = "shader/pass6/vs.lua",
	--     shader_fs_path = "shader/pass6/fs.lua",
	-- 	blendEnable = true
	-- }
}
function T1608802625400681067:init()
	self.bezierFunc1 = bezier({self.bezierParams1.x, self.bezierParams1.y, self.bezierParams1.z, self.bezierParams1.w})
	self.bezierFunc2 = bezier({self.bezierParams2.x, self.bezierParams2.y, self.bezierParams2.z, self.bezierParams2.w})
	self.bezierFunc3 = bezier({self.bezierParams3.x, self.bezierParams3.y, self.bezierParams3.z, self.bezierParams3.w})
	self.bezierFunc4 = bezier({self.bezierParams4.x, self.bezierParams4.y, self.bezierParams4.z, self.bezierParams4.w})
	local maxXNum = 0
	local maxYNum = 0
	if math.abs(self.PosRange1.x) > maxXNum then
		maxXNum = math.abs(self.PosRange1.x)
	end
	if math.abs(self.PosRange2.x) > maxXNum then
		maxXNum = math.abs(self.PosRange2.x)
	end
	if math.abs(self.PosRange3.x) > maxXNum then
		maxXNum = math.abs(self.PosRange3.x)
	end
	if math.abs(self.PosRange4.x) > maxXNum then
		maxXNum = math.abs(self.PosRange4.x)
	end
	if math.abs(self.PosRange1.z) > maxXNum then
		maxXNum = math.abs(self.PosRange1.z)
	end
	if math.abs(self.PosRange2.z) > maxXNum then
		maxXNum = math.abs(self.PosRange2.z)
	end
	if math.abs(self.PosRange3.z) > maxXNum then
		maxXNum = math.abs(self.PosRange3.z)
	end
	if math.abs(self.PosRange4.z) > maxXNum then
		maxXNum = math.abs(self.PosRange4.z)
	end
	if math.abs(self.PosRange1.y) > maxYNum then
		maxYNum = math.abs(self.PosRange1.y)
	end
	if math.abs(self.PosRange2.y) > maxYNum then
		maxYNum = math.abs(self.PosRange2.y)
	end
	if math.abs(self.PosRange3.y) > maxYNum then
		maxYNum = math.abs(self.PosRange3.y)
	end
	if math.abs(self.PosRange4.y) > maxYNum then
		maxYNum = math.abs(self.PosRange4.y)
	end
	if math.abs(self.PosRange1.w) > maxYNum then
		maxYNum = math.abs(self.PosRange1.w)
	end
	if math.abs(self.PosRange2.w) > maxYNum then
		maxYNum = math.abs(self.PosRange2.w)
	end
	if math.abs(self.PosRange3.w) > maxYNum then
		maxYNum = math.abs(self.PosRange3.w)
	end
	if math.abs(self.PosRange4.w) > maxYNum then
		maxYNum = math.abs(self.PosRange4.w)
	end
	-- self.text.targetRTExtraSize =
	-- 	Amaz.Vector2f(maxXNum * self.text.rect.width * self.extraSize, maxYNum * self.text.rect.height * self.extraSize)
	self.text.targetRTExtraSize = Amaz.Vector2f(0, self.text.rect.height * maxYNum)
	self.maxSize = Amaz.Vector2f(maxXNum * self.extraSize + 1, maxYNum * self.extraSize + 1)

	-- EffectSdk.LOG_LEVEL(8, " lrc ========>>: extra rt "..tostring(self.text.targetRTExtraSize))
	-- Amaz.LOGI("lrc extra rt", tostring(self.text.targetRTExtraSize))
	-- local ratio = Amaz.Vector2f(maxXNum* self.extraSize, maxYNum * self.extraSize)
	-- self.materials:get(0):setVec2("ratio", ratio)
	-- Amaz.LOGI("qdy_maxSize", tostring(self.maxSize))
	-- Amaz.LOGI("qdy_extraSize", tostring(self.extraSize))
	-- Amaz.LOGI("qdy_rect", tostring(self.text.rect))
end

function T1608802625400681067:onStart(comp)
    EffectSdk.LOG_LEVEL(8, "lrc ========>>: onstart "..tostring(0))

	self.text = comp.entity:getComponent("SDFText")
	if self.text == nil then
		local text = comp.entity:getComponent("Text")
		if text ~= nil then
			self.text = comp.entity:addComponent("SDFText")
			self.text:setTextWrapper(text)
		end
	end
	self.height = 0
	self.trans = comp.entity:getComponent("Transform")
	self.first = true
	self.renderer = nil
	if self.text ~= nil then
		self.renderer = comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = comp.entity:getComponent("Sprite2DRenderer")
	end
	local path = comp.entity.scene.assetMgr.rootDir
	for i = 1, #renderChain do
		-- Amaz.LOGI("wjs",path .. renderChain[i].shader_vs)
		-- local file = io.open(path .. renderChain[i].shader_vs, "r")
		renderChain[i].shader_vs = includeRelativePath(renderChain[i].shader_vs_path)
		-- file:close()
		-- local file2 = io.open(path .. renderChain[i].shader_fs, "r")
		renderChain[i].shader_fs = includeRelativePath(renderChain[i].shader_fs_path)
		-- file2:close()
	end
	-- Amaz.LOGI("wjs",1111111111)
	local Utils = includeRelativePath("Utils.lua")
	-- Amaz.LOGI("wjs",222222222)
	Utils.buildRenderChain(comp, renderChain, self.sharedMaterial)
	-- Amaz.LOGI("wjs",33333333333)
	-- Amaz.LOGI("wjs",tostring(self.sharedMaterial.xshader.passes:get(0).renderState.colorBlend.attachments:get(0).ColorBlendOp ))
	-- self.sharedMaterial:set
	-- Amaz.LOGI("qdy", "onStart")
end

if Amaz.Macros and Amaz.Macros.EditorSDK then
	---@function [UI(Button="Auto Play")]
	---@return void
	function T1608802625400681067:ButtonClip()
		if self.isAutoPlay then
			self.isAutoPlay = false
		else
			self.curTime = 0
			self.isAutoPlay = true
		end
	end

	function T1608802625400681067:onUpdate(comp, deltaTime)
		if self.isAutoPlay then
			self.curTime = self.curTime + deltaTime
			self.curTime = self.curTime % 3.0
		end
		-- self:init()
		self:seek(self.curTime)
		self.materials:get(0)["u_smoothRange"] = self.smoothRange
	end

	function T1608802625400681067:beforeEditorSave(comp)
		local prefab = comp.entity.scene.assetMgr:SyncLoad("anim.prefab")
		if prefab.entities:size() > 0 then
			local entity = prefab.entities:get(0)
			local prop = entity:getComponent("ScriptComponent").properties
			local vectorkeys = comp.properties:getVectorKeys()
			for i = 0, vectorkeys:size() - 1 do
				local key = vectorkeys:get(i)
				prop:set(key, comp.properties:get(key))
			end
		end
	end
end

function T1608802625400681067:seek(time)
	if self.first then
		local materials = Amaz.Vector()
		materials:pushBack(self.sharedMaterial)
		self.renderer.sharedMaterials = materials
		self.materials = self.renderer.materials
		if self.text ~= nil then
			self.text.renderToRT = true
		else
		end
		self:init()
		Amaz.LOGI("yyb ", tostring(self.text.targetRTExtraSize))

		self.first = false
	else
		self.renderer.materials = self.materials
	end

	-- local tex = self.materials:get(0):getTex("_MainTex")
	-- EffectSdk.LOG_LEVEL(8, tostring(time).." lrc ========>>:")
	-- self.text:forceTypeSetting()
	if self.text.chars:size() < 1 then
		return
	end
	-- Amaz.LOGI('yyb ',tostring(self.text.targetRTExtraSize))
	time = time % math.max(self.duration + 0.001, 0.0001)
	time = time / math.max(self.duration + 0.0, 0.0001)
	if time <= self.time1.x then
		self.materials:get(0):setFloat("u_alhpa1", 0)
	elseif time <= self.time1.y then
		-- EffectSdk.LOG_LEVEL(8, " lrc ========>>:u_pos1 "..time..' '..x1..' '..tostring(u_pos1))
		self.materials:get(0):setFloat("u_alhpa1", 0.35 * (1. - (self.time1.y - time) / (self.time1.y - self.time1.x)))
		local x1 = self.bezierFunc1(time - self.time1.x, 0, 1, self.time1.y - self.time1.x)
		local u_pos1 =
			Amaz.Vector2f(
			self.PosRange1.x + (self.PosRange1.z - self.PosRange1.x) * x1,
			self.PosRange1.y + (self.PosRange1.w - self.PosRange1.y) * x1
		)
		self.materials:get(0):setVec2("u_pos1", u_pos1)
	else
		-- EffectSdk.LOG_LEVEL(8, " lrc ========>>:u_pos111 "..time..' '..tostring(self.materials:get(0):getVec2("u_pos1")))
		self.materials:get(0):setFloat("u_alhpa1", 0.35)
		self.materials:get(0):setVec2("u_pos1", Amaz.Vector2f(self.PosRange1.z, self.PosRange1.w))
	end

	if time <= self.time2.x then
		self.materials:get(0):setFloat("u_alhpa2", 0)
	elseif time <= self.time2.y then
		-- EffectSdk.LOG_LEVEL(8, " lrc ========>>:u_pos2 "..tostring(u_pos2))
		self.materials:get(0):setFloat("u_alhpa2", 0.55 * (1. - (self.time2.y - time) / (self.time2.y - self.time2.x)))
		local x1 = self.bezierFunc2(time - self.time2.x, 0, 1, self.time2.y - self.time2.x)
		local u_pos2 =
			Amaz.Vector2f(
			self.PosRange2.x + (self.PosRange2.z - self.PosRange2.x) * x1,
			self.PosRange2.y + (self.PosRange2.w - self.PosRange2.y) * x1
		)
		self.materials:get(0):setVec2("u_pos2", u_pos2)
	else
		-- EffectSdk.LOG_LEVEL(8, " lrc ========>>:u_pos2 "..tostring(self.materials:get(0):getVec2("u_pos2")))
		self.materials:get(0):setFloat("u_alhpa2", 0.55)
		self.materials:get(0):setVec2("u_pos2", Amaz.Vector2f(self.PosRange2.z, self.PosRange2.w))
	end

	if time <= self.time3.x then
		self.materials:get(0):setFloat("u_alhpa3", 0)
	elseif time <= self.time3.y then
		-- EffectSdk.LOG_LEVEL(8, " lrc ========>>:u_pos3 "..tostring(u_pos3))
		self.materials:get(0):setFloat("u_alhpa3", 1.0 * (1. - (self.time3.y - time) / (self.time3.y - self.time3.x)))
		local x1 = self.bezierFunc3(time - self.time3.x, 0, 1, self.time3.y - self.time3.x)
		local u_pos3 =
			Amaz.Vector2f(
			self.PosRange3.x + (self.PosRange3.z - self.PosRange3.x) * x1,
			self.PosRange3.y + (self.PosRange3.w - self.PosRange3.y) * x1
		)
		self.materials:get(0):setVec2("u_pos3", u_pos3)
	else
		self.materials:get(0):setFloat("u_alhpa3",1.0)
		self.materials:get(0):setVec2("u_pos3", Amaz.Vector2f(self.PosRange3.z, self.PosRange3.w))
	end

	if time <= self.time4.x then
		self.materials:get(0):setFloat("u_alhpa4", 0)
	elseif time < self.time4.y then
		-- EffectSdk.LOG_LEVEL(8, " lrc ========>>:u_pos4  "..tostring(u_pos4))
		self.materials:get(0):setFloat("u_alhpa4", 1.0 * (1. - (self.time4.y - time) / (self.time4.y - self.time4.x)))
		local x1 = self.bezierFunc4(time - self.time4.x, 0, 1, self.time4.y - self.time4.x)
		local u_pos4 =
			Amaz.Vector2f(
			self.PosRange4.x + (self.PosRange4.z - self.PosRange4.x) * x1,
			self.PosRange4.y + (self.PosRange4.w - self.PosRange4.y) * x1
		)
		self.materials:get(0):setVec2("u_pos4", u_pos4)
	else
		self.materials:get(0):setFloat("u_alhpa4", 1)
		self.materials:get(0):setVec2("u_pos4", Amaz.Vector2f(self.PosRange4.z, self.PosRange4.w))
	end
	self.materials:get(0):setVec2("u_maxPos", self.maxSize)
end

function T1608802625400681067:setDuration(duration)
	self.duration = math.max(duration, 0.0001)
end

function T1608802625400681067:clear()
    EffectSdk.LOG_LEVEL(8, "lrc ========>>: clear "..tostring(0))
	if self.text ~= nil then
		local chars = self.text.chars
		for i = 1, chars:size() do
			local char = chars:get(i - 1)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
				char.color = Amaz.Vector4f(1, 1, 1, 1)
			end
		end
		self.text.chars = chars
		self.text.renderToRT = false
		-- self.clearState = true
		-- self.renderer.sharedMaterials = Amaz.Vector()
		self.text.targetRTExtraSize = Amaz.Vector2f(0, 0)
	end

	self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
	self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
	self.trans.localScale = Amaz.Vector3f(1, 1, 1)
end

function T1608802625400681067:onEnter()
    EffectSdk.LOG_LEVEL(8, "lrc ========>>: onenter "..tostring(0))
	self.first = true
	-- self.clearState = false

	-- self.text.renderToRT = true
end

function T1608802625400681067:onLeave()
    EffectSdk.LOG_LEVEL(8, "lrc ========>>: onleave "..tostring(0))
	if self.text ~= nil then
		self:clear()
	end
	self.first = true
end

exports.T1608802625400681067 = T1608802625400681067
return exports
