InfoSticker = {
            materials = {
                {
                    id = 0,
                    type = materialType.autoAtlas,
                    data = "9D969B9AED6E4EE285146D7553B4FFD4/2E67B2E94CF0415BAC83362E4ACBC0DD.json",
                    source = "9D969B9AED6E4EE285146D7553B4FFD4/1422AFB8174C41839158163C940E49CF.png"
                }
            },
            entity,
        }
        
        function InfoSticker:new()
            local o = {}
            setmetatable(o, self)
            self.__index = self
            local viewer = director:getViewer()
            local width = viewer:getWidth()
            local scale = width / 720.0 * 1.000000
            o.entity = scene:createEntity("infoSticker" .. math.random())
            o.entity:getTransform():setScale(scale)
            o.entity:addSpriteComponent():getSprite():setTexture(director:getTextureById(0))
            local controller = o.entity:addAnimatorComponent():getController()
            controller:setFps(6)
            EffectSdk.AnimationFactory.createFrameAnimation(controller, "frame")
            controller:getAnimationState("frame"):setLoop(true)
                     
local curve = EffectSdk.Line2D.create(EffectSdk.Vec2(0, 0), 5)
            EffectSdk.AnimationFactory.createScaleAnimation(controller, "easeInAnimation", curve, 0.2, false, 1.0)
            local curve = EffectSdk.Line2D.create(EffectSdk.Vec2(0, 1), -5)
            EffectSdk.AnimationFactory.createScaleAnimation(controller, "easeOutAnimation", curve, 0.2, false, 1.0)
            return o
        end